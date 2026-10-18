import os
import shutil
import hashlib
import difflib
from datetime import datetime
from memory.config_manager import WORKSPACE_DIR
from memory.memory_manager import MemoryManager
from core.confirm import ConfirmationGate
from core.undo import UndoManager


class FileController:
    MAX_READ_SIZE = 2 * 1024 * 1024  # 2 MB guardrail

    def __init__(self, memory: MemoryManager, confirm: ConfirmationGate, undo: UndoManager):
        self.memory = memory
        self.confirm = confirm
        self.undo = undo

    def _sandbox_path(self, filename: str) -> str:
        safe_name = os.path.basename(filename.strip())
        return os.path.join(WORKSPACE_DIR, safe_name)

    def search_files(self, keyword: str = "", extension: str = "") -> str:
        """Searches files in ATLAS_Workspace by keyword, extension, and modified timestamp."""
        entries = []
        for fname in os.listdir(WORKSPACE_DIR):
            if fname.startswith("."):
                continue
            fpath = os.path.join(WORKSPACE_DIR, fname)
            if not os.path.isfile(fpath):
                continue
            if keyword and keyword.lower() not in fname.lower():
                continue
            if extension and not fname.lower().endswith(extension.lower()):
                continue
            mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d %H:%M")
            size_kb = round(os.path.getsize(fpath) / 1024, 1)
            entries.append(f"{fname} (Modified: {mtime}, Size: {size_kb} KB)")

        self.memory.log_audit("search_files", 0, "SUCCESS", f"kw='{keyword}', ext='{extension}', matches={len(entries)}")
        if not entries:
            return f"No files found in workspace matching keyword='{keyword}' ext='{extension}'."
        return "Workspace Files:\n" + "\n".join(entries)

    def read_document(self, filename: str) -> str:
        """Reads a workspace document wrapped in untrusted content isolation markers."""
        filepath = self._sandbox_path(filename)
        if not os.path.exists(filepath):
            return f"FAILED: File '{os.path.basename(filepath)}' does not exist in ATLAS_Workspace."
        if os.path.getsize(filepath) > self.MAX_READ_SIZE:
            return "FAILED: File exceeds 2 MB safety read limit."
        try:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            self.memory.log_audit("read_document", 0, "VERIFIED", os.path.basename(filepath))
            return (
                f"VERIFIED (Path: {filepath}):\n"
                f"[UNTRUSTED_CONTENT_START]\n{content}\n[UNTRUSTED_CONTENT_END]"
            )
        except Exception as e:
            return f"FAILED: {e}"

    def create_file(self, filename: str, content: str) -> str:
        """Creates or overwrites a note/report in ATLAS_Workspace with automatic backup and verification."""
        safe_name = "".join([c for c in os.path.basename(filename) if c.isalnum() or c in " ._-"]).rstrip()
        if not safe_name:
            return "FAILED: Invalid filename."
        if "." not in safe_name:
            safe_name += ".md"
        filepath = os.path.join(WORKSPACE_DIR, safe_name)

        if os.path.exists(filepath):
            approved, reason = self.confirm.request_approval(
                action="Overwrite Existing Document",
                target=filepath,
                scope=f"New content length: {len(content)} chars",
                consequences="Replaces existing file content (a backup copy will be saved in .backups).",
                risk_level=2,
            )
            if not approved:
                self.memory.log_audit("create_file", 2, "DENIED", safe_name)
                return f"CANCELLED: Overwrite denied ({reason})."
            self.undo.backup_file(filepath, "overwrite_file")
            is_new = False
        else:
            is_new = True

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            if os.path.exists(filepath):
                if is_new:
                    self.undo.record_created_file(filepath)
                self.memory.log_audit("create_file", 1, "VERIFIED", safe_name)
                return f"VERIFIED: Saved '{safe_name}' ({os.path.getsize(filepath)} bytes) in ATLAS_Workspace."
            return "FAILED: File could not be verified on disk after write."
        except Exception as e:
            return f"FAILED: {e}"

    def move_file(self, source_filename: str, target_filename: str) -> str:
        """Renames or moves a file within ATLAS_Workspace after Level 2 approval and backup."""
        src = self._sandbox_path(source_filename)
        dst = self._sandbox_path(target_filename)
        if not os.path.exists(src):
            return f"FAILED: Source file '{os.path.basename(src)}' not found."

        approved, reason = self.confirm.request_approval(
            action="Rename / Move File",
            target=f"{os.path.basename(src)} -> {os.path.basename(dst)}",
            scope="ATLAS_Workspace directory",
            consequences="Changes the filename; backup preserved.",
            risk_level=2,
        )
        if not approved:
            return f"CANCELLED: Move denied ({reason})."

        self.undo.backup_file(src, "move_file", target_path=dst)
        shutil.move(src, dst)
        if os.path.exists(dst) and not os.path.exists(src):
            self.memory.log_audit("move_file", 2, "VERIFIED", f"{os.path.basename(src)}->{os.path.basename(dst)}")
            return f"VERIFIED: Renamed/moved '{os.path.basename(src)}' to '{os.path.basename(dst)}'."
        return "FAILED: Move verification failed."

    def compare_documents(self, file_a: str, file_b: str) -> str:
        """Compares two workspace documents and returns a unified diff summary."""
        path_a = self._sandbox_path(file_a)
        path_b = self._sandbox_path(file_b)
        if not os.path.exists(path_a) or not os.path.exists(path_b):
            return "FAILED: Both files must exist in ATLAS_Workspace to compare."

        with open(path_a, "r", encoding="utf-8", errors="replace") as fa:
            lines_a = fa.readlines()
        with open(path_b, "r", encoding="utf-8", errors="replace") as fb:
            lines_b = fb.readlines()

        diff = list(difflib.unified_diff(lines_a, lines_b, fromfile=file_a, tofile=file_b, lineterm=""))
        self.memory.log_audit("compare_documents", 0, "VERIFIED", f"{file_a} vs {file_b}")
        if not diff:
            return f"VERIFIED: '{file_a}' and '{file_b}' are identical."
        preview = "\n".join(diff[:60])
        return f"VERIFIED Diff ({file_a} vs {file_b}):\n{preview}"

    def find_duplicates_or_large_files(self, large_threshold_kb: int = 500) -> str:
        """Scans ATLAS_Workspace for exact SHA-256 duplicates and large files without auto-deleting."""
        hashes = {}
        duplicates = []
        large_files = []

        for fname in os.listdir(WORKSPACE_DIR):
            if fname.startswith("."):
                continue
            fpath = os.path.join(WORKSPACE_DIR, fname)
            if not os.path.isfile(fpath):
                continue
            size_kb = os.path.getsize(fpath) / 1024.0
            if size_kb >= large_threshold_kb:
                large_files.append(f"{fname} ({round(size_kb, 1)} KB)")

            h = hashlib.sha256()
            with open(fpath, "rb") as f:
                while chunk := f.read(65536):
                    h.update(chunk)
            digest = h.hexdigest()
            if digest in hashes:
                duplicates.append(f"'{fname}' is a duplicate of '{hashes[digest]}'")
            else:
                hashes[digest] = fname

        report = []
        report.append("Duplicates found: " + (", ".join(duplicates) if duplicates else "None"))
        report.append(f"Files >= {large_threshold_kb} KB: " + (", ".join(large_files) if large_files else "None"))
        report.append("Note: No files were deleted automatically. Ask to delete specific files if desired.")
        self.memory.log_audit("find_duplicates_or_large_files", 0, "VERIFIED", f"dups={len(duplicates)}")
        return "\n".join(report)

    def delete_file(self, filename: str) -> str:
        """Deletes a file in ATLAS_Workspace after Level 3 approval and backup creation."""
        filepath = self._sandbox_path(filename)
        if not os.path.exists(filepath):
            return f"FAILED: File '{os.path.basename(filepath)}' not found."

        approved, reason = self.confirm.request_approval(
            action="Delete Workspace File",
            target=filepath,
            scope=f"Size: {os.path.getsize(filepath)} bytes",
            consequences="Removes file from workspace (a recovery backup is saved in .backups).",
            risk_level=3,
        )
        if not approved:
            self.memory.log_audit("delete_file", 3, "DENIED", os.path.basename(filepath))
            return f"CANCELLED: File deletion denied ({reason})."

        self.undo.backup_file(filepath, "delete_file")
        os.remove(filepath)
        if not os.path.exists(filepath):
            self.memory.log_audit("delete_file", 3, "VERIFIED", os.path.basename(filepath))
            return f"VERIFIED: Deleted '{os.path.basename(filepath)}' (Undo backup available)."
        return "FAILED: File still present on disk."