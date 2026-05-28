import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config as cfg


def test_model_name_is_set():
    assert cfg.MODEL_NAME == "gpt-4o-mini"


def test_embedding_model_is_set():
    assert cfg.EMBEDDING_MODEL == "text-embedding-ada-002"


def test_all_constants_have_values():
    assert cfg.CHUNK_SIZE > 0
    assert cfg.CHUNK_OVERLAP >= 0
    assert cfg.COMPLIANCE_TEMPERATURE >= 0
    assert cfg.COMPLIANCE_MAX_TOKENS > 0
    assert cfg.RELOCATION_TEMPERATURE >= 0
    assert cfg.RELOCATION_MAX_TOKENS > 0
    assert cfg.RAG_SEARCH_K > 0
    assert cfg.BRAVE_SEARCH_COUNT > 0
    assert cfg.BRAVE_TIMEOUT > 0
    assert cfg.OPENAI_TIMEOUT > 0
    assert cfg.RETRY_OPENAI_ATTEMPTS > 0
    assert cfg.RETRY_BRAVE_ATTEMPTS > 0
    assert cfg.RETRY_MIN_WAIT > 0
    assert cfg.RETRY_MAX_WAIT > 0


def test_env_path_exists():
    assert str(cfg.ENV_PATH).endswith(".env")
