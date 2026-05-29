import json
import threading
from pathlib import Path

from langchain_openai import OpenAIEmbeddings

CACHE_FILE = Path(__file__).resolve().parent.parent / "agent_cache.json"

_embeddings = None
_embeddings_lock = threading.Lock()


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        with _embeddings_lock:
            if _embeddings is None:
                _embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")
    return _embeddings


def warm_embeddings():
    t = threading.Thread(target=get_embeddings, daemon=True)
    t.start()
    return t


class AgentCache:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._data = {}
            cls._instance._lock = threading.Lock()
            cls._instance._load()
        return cls._instance

    def _load(self):
        if CACHE_FILE.exists():
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                self._data = json.load(f)

    def _save(self):
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key: str):
        return self._data.get(key)

    def set(self, key: str, value):
        self._data[key] = value
        self._save()

    @staticmethod
    def make_key(*parts) -> str:
        return ":".join(str(p) for p in parts)
