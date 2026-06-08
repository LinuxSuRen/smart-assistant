import glob
import json
import os
from datetime import datetime, timezone

MEMORY_FILE_PREFIX = "conv_"
MEMORY_FILE_PATTERN = "conv_*.json"
ASSISTANT_NAME_FILE = "assistant_name.txt"
DEFAULT_ASSISTANT_NAME = "Lisa"


class MemoryStore:
    def __init__(self, memory_dir: str = "data/memory", max_memories: int = 20):
        self.memory_dir = memory_dir
        self.max_memories = max_memories
        self.memories: list[dict] = []
        self._load()

    def _load(self):
        if not os.path.isdir(self.memory_dir):
            return
        files = sorted(glob.glob(os.path.join(self.memory_dir, MEMORY_FILE_PATTERN)))
        for fpath in files:
            try:
                with open(fpath, "r") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "summary" in data:
                        self.memories.append(data)
            except (json.JSONDecodeError, OSError):
                pass

    def _save_one(self, summary: str) -> str:
        os.makedirs(self.memory_dir, exist_ok=True)
        ts = datetime.now(timezone.utc)
        filename = f"{MEMORY_FILE_PREFIX}{ts.strftime('%Y%m%d_%H%M%S')}.json"
        fpath = os.path.join(self.memory_dir, filename)
        entry = {
            "timestamp": ts.isoformat(),
            "summary": summary.strip(),
        }
        with open(fpath, "w") as f:
            json.dump(entry, f, ensure_ascii=False, indent=2)
        return fpath

    def _prune(self):
        files = sorted(glob.glob(os.path.join(self.memory_dir, MEMORY_FILE_PATTERN)))
        while len(files) > self.max_memories:
            oldest = files.pop(0)
            try:
                os.remove(oldest)
            except OSError:
                pass
        self.memories = self.memories[-self.max_memories:]

    def save_memory(self, summary: str):
        summary = summary.strip()
        if not summary:
            return
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
        }
        self.memories.append(entry)
        self._save_one(summary)
        self._prune()

    def get_memory_context(self) -> str:
        if not self.memories:
            return ""
        lines = ["Previous conversation memories:"]
        for i, m in enumerate(self.memories, 1):
            lines.append(f"- {m['summary']}")
        return "\n".join(lines)

    def get_assistant_name(self) -> str:
        fpath = os.path.join(self.memory_dir, ASSISTANT_NAME_FILE)
        if os.path.isfile(fpath):
            try:
                with open(fpath, "r") as f:
                    name = f.read().strip()
                    if name:
                        return name
            except OSError:
                pass
        return DEFAULT_ASSISTANT_NAME

    def set_assistant_name(self, name: str):
        name = name.strip()
        if not name:
            return
        os.makedirs(self.memory_dir, exist_ok=True)
        fpath = os.path.join(self.memory_dir, ASSISTANT_NAME_FILE)
        with open(fpath, "w") as f:
            f.write(name)
