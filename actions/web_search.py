import re
import json
import webbrowser
import urllib.request
import urllib.parse
from datetime import datetime
from memory.memory_manager import MemoryManager


class WebResearchActions:
    def __init__(self, memory: MemoryManager):
        self.memory = memory

    def web_search(self, query: str) -> str:
        """Searches Wikipedia and DuckDuckGo Instant Answers with source links and date checked."""
        checked_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        findings = []

        # 1. Wikipedia API with URLs
        try:
            safe_q = urllib.parse.quote(query)
            url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={safe_q}&utf8=&format=json"
            req = urllib.request.Request(url, headers={"User-Agent": "ATLAS_Operator/2.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode())
                for item in data.get("query", {}).get("search", [])[:3]:
                    title = item["title"]
                    snippet = re.sub(r"<[^>]+>", "", item["snippet"])
                    link = f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
                    findings.append(f"- [Wikipedia: {title}]({link}): {snippet}")
        except Exception:
            pass

        # 2. DuckDuckGo Instant Answer API
        try:
            ddg_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1"
            req = urllib.request.Request(ddg_url, headers={"User-Agent": "ATLAS_Operator/2.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                ddg = json.loads(resp.read().decode())
                if ddg.get("AbstractText"):
                    findings.append(f"- [DuckDuckGo Abstract]({ddg.get('AbstractURL', '')}): {ddg['AbstractText']}")
        except Exception:
            pass

        self.memory.log_audit("web_search", 0, "VERIFIED", f"query='{query}', sources={len(findings)}")
        if not findings:
            return f"No verified web results found for '{query}' (Checked: {checked_at})."

        joined = "\n".join(findings)
        return (
            f"Web Research Results (Checked: {checked_at}):\n"
            f"[UNTRUSTED_CONTENT_START]\n{joined}\n[UNTRUSTED_CONTENT_END]"
        )

    def extract_webpage_text(self, url: str) -> str:
        """Downloads and extracts readable text from a URL inside untrusted isolation markers."""
        if not url.startswith(("http://", "https://")):
            return "FAILED: URL must start with http:// or https://"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "ATLAS_Operator/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")
            # Strip scripts and styles
            clean = re.sub(r"<(script|style).*?>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
            clean = re.sub(r"<[^>]+>", " ", clean)
            clean = re.sub(r"\s+", " ", clean).strip()[:4000]
            checked_at = datetime.now().strftime("%Y-%m-%d %H:%M")
            self.memory.log_audit("extract_webpage_text", 0, "VERIFIED", url)
            return (
                f"Extracted Page Content from {url} (Checked: {checked_at}):\n"
                f"[UNTRUSTED_CONTENT_START]\n{clean}\n[UNTRUSTED_CONTENT_END]"
            )
        except Exception as e:
            return f"FAILED: Could not extract webpage - {e}"

    def open_page(self, url: str) -> str:
        """Opens a URL in the default browser."""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        webbrowser.open(url)
        self.memory.log_audit("open_page", 1, "VERIFIED", url)
        return f"VERIFIED: Opened {url} in browser."