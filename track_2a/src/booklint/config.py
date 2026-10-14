import os
import tempfile
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
    timeout: float = 60.0

    @classmethod
    def from_env(cls, model=None):
        """OST's evaluation injects BASE_URL and API_KEY; they win over LLM_BASE_URL / LLM_API_KEY and .env."""
        load_dotenv(os.environ.get("BOOKLINT_ENV_FILE", ".env"))
        base_url = os.environ.get("BASE_URL") or os.environ.get("LLM_BASE_URL")
        api_key = os.environ.get("API_KEY") or os.environ.get("LLM_API_KEY")
        if not base_url or not api_key:
            missing = [
                k for k, v in (("BASE_URL", base_url), ("API_KEY", api_key)) if not v
            ]
            raise SystemExit(
                f"Missing environment variables: {', '.join(missing)} (or LLM_BASE_URL / LLM_API_KEY, see .env.example)"
            )
        return cls(
            model=model
            or os.environ.get("LLM_NAME")
            or os.environ.get("MODEL")
            or "apertus-v1.5-8b",
            base_url=base_url,
            api_key=api_key,
            cache_dir=cache_dir(),
            timeout=float(os.environ.get("LLM_TIMEOUT", "60")),
        )


def cache_dir():
    """CACHE_DIR, else .cache; a cache that cannot be written (read-only mount) falls back to the temp dir."""
    load_dotenv(os.environ.get("BOOKLINT_ENV_FILE", ".env"))
    path = Path(os.environ.get("CACHE_DIR", ".cache"))
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".write-test"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
    except OSError:
        path = Path(tempfile.gettempdir()) / "booklint-cache"
        path.mkdir(parents=True, exist_ok=True)
    return path
