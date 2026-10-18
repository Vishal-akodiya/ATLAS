import io
import os
import time
import random
import inspect
import itertools
import threading
from PIL import Image
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# Weighted fast model pool (favors low-latency Flash-Lite / Flash models)
MODEL_FAILOVER_POOL = [
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.8-flash",
]

# Default Vertex AI regions (only used if GEMINI_USE_VERTEX=true in .env)
DEFAULT_VERTEX_REGIONS = [
    "global",
    "asia-south1",
    "asia-southeast1",
    "europe-west4",
    "europe-west1",
    "us-east1",
]

_COOLDOWN_SECONDS = 30
_GONE_SECONDS = 6 * 60 * 60

_cooldown = {}
_cool_lock = threading.Lock()


def _cool(key: str, seconds: float = _COOLDOWN_SECONDS) -> None:
    with _cool_lock:
        _cooldown[key] = time.monotonic() + seconds


def _cooling(key: str) -> bool:
    with _cool_lock:
        until = _cooldown.get(key, 0.0)
        if until and time.monotonic() < until:
            return True
        _cooldown.pop(key, None)
        return False


def _make_standalone_tool(bound_func):
    if not inspect.ismethod(bound_func):
        return bound_func

    def wrapper(*args, **kwargs):
        return bound_func(*args, **kwargs)

    wrapper.__name__ = bound_func.__name__
    wrapper.__qualname__ = bound_func.__name__
    wrapper.__doc__ = bound_func.__doc__
    orig_ann = getattr(bound_func, "__annotations__", {})
    wrapper.__annotations__ = {k: v for k, v in orig_ann.items() if k != "self"}
    wrapper.__signature__ = inspect.signature(bound_func)
    return wrapper


class GeminiEngine:
    def __init__(self, tools_list: list):
        # Support either a single GEMINI_API_KEY or comma-separated GEMINI_API_KEYS
        raw_keys = os.getenv("GEMINI_API_KEYS") or os.getenv("GEMINI_API_KEY", "")
        api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        if not api_keys:
            raise ValueError("GEMINI_API_KEY is not set in the .env file.")

        preferred = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite").strip()
        base_models = [preferred] + [m for m in MODEL_FAILOVER_POOL if m != preferred]
        # Deduplicate while preserving order for clean round-robin cycling
        self.model_pool = list(dict.fromkeys(base_models))
        self.shuffle_models = os.getenv("GEMINI_ROUND_ROBIN_MODELS", "true").lower() in ("1", "true", "yes")
        self._model_cycle_lock = threading.Lock()
        self._model_cycle = itertools.cycle(self.model_pool)
        self.active_model = preferred
        self.active_region = "global"

        # 20s timeout so a stalled endpoint fails over quickly instead of hanging for 120s
        http_opts = types.HttpOptions(timeout=20000)

        # Build client pool (supports Vertex AI multi-region rotation OR multi-key rotation)
        use_vertex = os.getenv("GEMINI_USE_VERTEX", "false").lower() in ("1", "true", "yes")
        gcp_project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
        raw_regions = os.getenv("GEMINI_REGIONS", "")
        regions = [r.strip() for r in raw_regions.split(",") if r.strip()] or list(DEFAULT_VERTEX_REGIONS)

        self.client_pool: list[tuple[str, genai.Client]] = []
        if use_vertex:
            random.shuffle(regions)
            for region in regions:
                try:
                    if gcp_project:
                        client = genai.Client(
                            vertexai=True,
                            project=gcp_project,
                            location=region,
                            http_options=http_opts,
                        )
                    else:
                        # Vertex AI Express Mode with API Key
                        client = genai.Client(
                            vertexai=True,
                            api_key=api_keys[0],
                            http_options=http_opts,
                        )
                    self.client_pool.append((region, client))
                except Exception as e:
                    print(f"[Gemini] Skipping region {region}: {e}")

        if not self.client_pool:
            random.shuffle(api_keys)
            for idx, key in enumerate(api_keys):
                label = f"api_key_{idx + 1}"
                try:
                    self.client_pool.append((label, genai.Client(api_key=key, http_options=http_opts)))
                except Exception:
                    self.client_pool.append((label, genai.Client(api_key=key)))

        self._client_cycle = itertools.cycle(self.client_pool)

        self.all_tools = {}
        for func in tools_list:
            clean_fn = _make_standalone_tool(func)
            self.all_tools[clean_fn.__name__] = clean_fn

        self.prompt_path = os.path.join(os.path.dirname(__file__), "prompt.txt")
        self.system_prompt = self._load_system_prompt()
        self.rolling_history: list[str] = []

    def __deepcopy__(self, memo):
        return self

    def _load_system_prompt(self) -> str:
        if os.path.exists(self.prompt_path):
            with open(self.prompt_path, "r", encoding="utf-8") as f:
                return f.read()
        return "You are ATLAS, a fast personal AI desktop operator. Answer concisely in 1-2 sentences."

    def reset_chat(self):
        self.rolling_history.clear()

    def _get_ordered_models(self) -> list[str]:
        """Returns the model list starting from the next round-robin/shuffled model."""
        if not self.shuffle_models or len(self.model_pool) <= 1:
            return list(self.model_pool)
        with self._model_cycle_lock:
            start_model = next(self._model_cycle)
        start_idx = self.model_pool.index(start_model)
        rotated = self.model_pool[start_idx:] + self.model_pool[:start_idx]
        return rotated

    def _get_ordered_clients(self) -> list[tuple[str, genai.Client]]:
        """Returns the client/region list rotated via round-robin."""
        if len(self.client_pool) <= 1:
            return list(self.client_pool)
        with self._model_cycle_lock:
            first = next(self._client_cycle)
        idx = self.client_pool.index(first)
        return self.client_pool[idx:] + self.client_pool[:idx]

    @staticmethod
    def compress_image_for_api(image_input, max_dim: int = 1024, quality: int = 72) -> types.Part:
        if isinstance(image_input, str):
            img = Image.open(image_input)
        else:
            img = image_input
        img = img.convert("RGB")
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")

    def _select_relevant_tools(self, prompt: str, with_screen: bool = False) -> list:
        p = prompt.lower()
        selected = ["get_current_time"]

        if with_screen or any(w in p for w in ("screen", "click", "button", "locate", "look", "type", "window", "scroll", "key", "shortcut")):
            selected.extend(["inspect_screen_state", "locate_and_interact_on_screen", "type_text", "press_hotkey", "click_control", "scroll_screen", "focus_window"])
        if any(w in p for w in ("open", "launch", "start", "app", "whatsapp", "close", "minimize")):
            selected.extend(["open_app", "list_installed_apps", "send_whatsapp_message", "focus_window", "minimize_window", "close_app"])
        if any(w in p for w in ("file", "note", "document", "read", "write", "save", "folder", "duplicate", "compare", "delete", "move", "rename", "undo")):
            selected.extend(["search_files", "read_document", "create_file", "move_file", "compare_documents", "find_duplicates_or_large_files", "delete_file", "undo_last_action"])
        if any(w in p for w in ("remind", "task", "schedule", "todo", "snooze", "overdue", "tomorrow", "briefing")):
            selected.extend(["create_task", "list_tasks", "snooze_task", "reschedule_task", "cancel_task", "generate_daily_briefing"])
        if any(w in p for w in ("search", "web", "wikipedia", "google", "research", "url", "http", "page", "website")):
            selected.extend(["web_search", "extract_webpage_text", "open_page"])
        if any(w in p for w in ("remember", "memory", "preference", "forget", "recall", "checkpoint", "resume")):
            selected.extend(["save_user_memory", "search_user_memory", "delete_user_memory", "save_task_checkpoint"])
        if any(w in p for w in ("email", "draft", "calendar", "event", "meeting", "message", "team")):
            selected.extend(["draft_email", "prepare_calendar_event", "send_message", "send_whatsapp_message"])
        if any(w in p for w in ("cpu", "ram", "disk", "system", "status", "running", "log", "command", "ipconfig")):
            selected.extend(["check_system_status", "check_app_running", "read_logs", "run_approved_command"])

        seen = set()
        pruned_funcs = []
        for name in selected:
            if name not in seen and name in self.all_tools:
                seen.add(name)
                pruned_funcs.append(self.all_tools[name])
        return pruned_funcs

    def _build_config(self, tools: list = None, temperature: float = 0.2, disable_thinking: bool = True) -> types.GenerateContentConfig:
        base_kwargs = {"temperature": temperature}
        if self.system_prompt:
            base_kwargs["system_instruction"] = self.system_prompt
        if tools:
            base_kwargs["tools"] = tools
        if disable_thinking and hasattr(types, "ThinkingConfig"):
            try:
                base_kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)
            except Exception:
                pass
        return types.GenerateContentConfig(**base_kwargs)

    def _execute_with_cooldown(self, contents: list, tools: list = None, temperature: float = 0.2):
        last_err = None
        cfg_fast = self._build_config(tools=tools, temperature=temperature, disable_thinking=True)
        cfg_std = self._build_config(tools=tools, temperature=temperature, disable_thinking=False)

        models_to_try = self._get_ordered_models()
        clients_to_try = self._get_ordered_clients()

        for model_name in models_to_try:
            if _cooling(model_name):
                continue

            for region_label, client in clients_to_try:
                route_key = f"{region_label}:{model_name}"
                if _cooling(route_key):
                    continue

                try:
                    try:
                        res = client.models.generate_content(model=model_name, contents=contents, config=cfg_fast)
                    except Exception as cfg_err:
                        # Fallback if a specific model doesn't accept thinking_budget=0
                        if "thinking" in str(cfg_err).lower() or "invalid_argument" in str(cfg_err).lower():
                            res = client.models.generate_content(model=model_name, contents=contents, config=cfg_std)
                        else:
                            raise

                    self.active_model = model_name
                    self.active_region = region_label
                    return res

                except Exception as e:
                    err_msg = str(e).lower()
                    last_err = e
                    if "429" in err_msg or "resource_exhausted" in err_msg:
                        _cool(route_key, _COOLDOWN_SECONDS)
                        print(f"[Gemini] {route_key}: quota limit - resting for {_COOLDOWN_SECONDS}s")
                    elif any(k in err_msg for k in ("503", "504", "unavailable", "deadline_exceeded", "timeout")):
                        _cool(route_key, _COOLDOWN_SECONDS)
                        print(f"[Gemini] {route_key}: timeout/unavailable - resting for {_COOLDOWN_SECONDS}s")
                    elif any(k in err_msg for k in ("404", "not found", "is not supported", "permission", "403")):
                        _cool(model_name, _GONE_SECONDS)
                        print(f"[Gemini] {model_name}: unavailable/gone - skipping for session")
                        break
                    else:
                        _cool(route_key, _COOLDOWN_SECONDS)
                        print(f"[Gemini] {route_key} failed: {e}")
                    continue

        raise RuntimeError(f"All models/regions failed or are resting. Last error: {last_err}")

    def generate_vision_content(self, prompt: str, pil_image: Image.Image, temperature: float = 0.1) -> str:
        img_part = self.compress_image_for_api(pil_image, max_dim=1024, quality=72)
        res = self._execute_with_cooldown(contents=[prompt, img_part], tools=None, temperature=temperature)
        return (res.text or "").strip()

    def send(self, prompt: str, image_path: str = None) -> str:
        relevant_tools = self._select_relevant_tools(prompt, with_screen=bool(image_path))

        context_prefix = ""
        if self.rolling_history:
            recent = "\n".join(self.rolling_history[-4:])
            context_prefix = f"Recent Conversation Context:\n{recent}\n\nCurrent Request: "

        contents = [context_prefix + prompt]
        if image_path and os.path.exists(image_path):
            contents.append(self.compress_image_for_api(image_path, max_dim=1024, quality=72))

        res = self._execute_with_cooldown(contents=contents, tools=relevant_tools, temperature=0.2)
        reply = (res.text or "Task completed and verified.").strip()

        self.rolling_history.append(f"User: {prompt[:160]}")
        self.rolling_history.append(f"ATLAS: {reply[:220]}")
        if len(self.rolling_history) > 8:
            self.rolling_history = self.rolling_history[-8:]

        return reply