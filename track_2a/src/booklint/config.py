import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path):
    path = Path(path)
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass
class Settings:
    model: str
    base_url: str
    api_key: str
    cache_dir: Path
    timeout: float = 120.0

    @classmethod
    def from_env(cls, model=None):
        load_dotenv(os.environ.get("BOOKLINT_ENV_FILE", ".env"))
        missing = [k for k in ("LLM_BASE_URL", "LLM_API_KEY") if not os.environ.get(k)]
        if missing:
            raise SystemExit(
                f"Missing environment variables: {', '.join(missing)} (see .env.example)"
            )
        return cls(
            model=model or os.environ.get("LLM_NAME", "apertus-v1.5-8b"),
            base_url=os.environ["LLM_BASE_URL"],
            api_key=os.environ["LLM_API_KEY"],
            cache_dir=Path(os.environ.get("CACHE_DIR", ".cache")),
            timeout=float(os.environ.get("LLM_TIMEOUT", "120")),
        )


def cache_dir():
    load_dotenv(os.environ.get("BOOKLINT_ENV_FILE", ".env"))
    path = Path(os.environ.get("CACHE_DIR", ".cache"))
    path.mkdir(parents=True, exist_ok=True)
    return path
