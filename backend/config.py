import sys
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "globaltalent"))


class Settings(BaseSettings):
    db_path: Path = Path(__file__).resolve().parent.parent / "cases.db"
    upload_dir: Path = Path(__file__).resolve().parent.parent / "uploads"
    cache_ttl: int = 3600
    cache_max_size: int = 200
    rate_limit_per_minute: int = 60
    max_upload_mb: int = 10
    max_concurrent_cases: int = 10
    cors_origins: list[str] = ["*"]
    housekeeper_interval: int = 300
    sse_heartbeat: int = 15
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    slack_channel_id: str = ""
    slack_candidate_channel_id: str = ""
    slack_manager_id: str = ""
    maestro_webhook_secret: str = "maestro-secret-change-me"

    model_config = {"env_prefix": "GT_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
DB_PATH = settings.db_path
UPLOAD_DIR = settings.upload_dir
UPLOAD_DIR.mkdir(exist_ok=True)
