import json
from pathlib import Path
from typing import Dict, List, Optional, Any

class Manifest:
    def __init__(self, data: Dict[str, Any]):
        self.data = data
        # Index entries by corpus_relative_path for quick lookups
        self._by_corpus_path = {
            entry["corpus_relative_path"]: entry
            for entry in self.data.get("entries", [])
        }

    @classmethod
    def load(cls, manifest_path: str) -> "Manifest":
        with open(manifest_path, "r", encoding="utf-8") as f:
            return cls(json.load(f))

    def get_entry_by_path(self, corpus_relative_path: str) -> Optional[Dict[str, Any]]:
        """
        Lookup a manifest entry given the path returned by QMD.
        The path is expected to be relative to the corpus root.
        """
        # QMD might return paths starting with ./ or / depending on how it was invoked,
        # but since we set collection root strictly, they should be relative paths like
        # "skill_id/SKILL.md".
        path_str = Path(corpus_relative_path).as_posix()
        if path_str.startswith("./"):
            path_str = path_str[2:]
        return self._by_corpus_path.get(path_str)
