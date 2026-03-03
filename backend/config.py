"""Configuration for the LLM Council.

Supports runtime reload and JSON persistence via data/config.json.
Falls back to environment variables when no config file exists.
"""

import copy
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CONFIG_FILE = Path("data/config.json")
DATA_DIR = "data/conversations"

# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------
_config: dict = {}


def _json_map(env_name: str) -> dict:
    """Parse a JSON dict from an environment variable."""
    raw = os.getenv(env_name, "{}")
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _load_env_defaults() -> dict:
    """Build a config dict from all current environment variables."""
    council_models_raw = os.getenv(
        "COUNCIL_MODELS",
        "openai/gpt-5.1,google/gemini-3-pro-preview,anthropic/claude-sonnet-4.5,x-ai/grok-4",
    )
    council_models = [m.strip() for m in council_models_raw.split(",") if m.strip()]

    return {
        "llm_provider": os.getenv("LLM_PROVIDER", "openrouter").strip().lower(),
        "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
        "openrouter_api_url": os.getenv(
            "OPENROUTER_API_URL",
            "https://openrouter.ai/api/v1/chat/completions",
        ),
        "azure_foundry_endpoint": os.getenv("AZURE_FOUNDRY_ENDPOINT", "").rstrip("/"),
        "azure_foundry_api_key": os.getenv("AZURE_FOUNDRY_API_KEY"),
        "azure_foundry_api_version": os.getenv("AZURE_FOUNDRY_API_VERSION", "2024-10-21"),
        "azure_foundry_deployment_map": _json_map("AZURE_FOUNDRY_DEPLOYMENT_MAP"),
        "azure_foundry_endpoint_map": _json_map("AZURE_FOUNDRY_ENDPOINT_MAP"),
        "azure_foundry_api_key_map": _json_map("AZURE_FOUNDRY_API_KEY_MAP"),
        "azure_foundry_algorithm_endpoint_map": _json_map("AZURE_FOUNDRY_ALGORITHM_ENDPOINT_MAP"),
        "azure_foundry_algorithm_api_key_map": _json_map("AZURE_FOUNDRY_ALGORITHM_API_KEY_MAP"),
        "council_models": council_models,
        "chairman_model": os.getenv("CHAIRMAN_MODEL", "google/gemini-3-pro-preview"),
        "council_algorithm": os.getenv("COUNCIL_ALGORITHM", "peer_review").strip().lower(),
        "rank_aggregation_method": os.getenv("RANK_AGGREGATION_METHOD", "average_rank").strip().lower(),
    }


def reload_config() -> None:
    """Load config from config.json if it exists, otherwise from env defaults."""
    global _config
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                loaded = json.load(f)
            defaults = _load_env_defaults()
            defaults.update(loaded)
            _config = defaults
        except (json.JSONDecodeError, OSError) as exc:
            print(f"WARNING: Failed to load {CONFIG_FILE} ({exc}), falling back to env defaults.")
            _config = _load_env_defaults()
    else:
        _config = _load_env_defaults()


def save_config(new_config: dict) -> None:
    """Write *new_config* to config.json and reload."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    merged = _load_env_defaults()
    merged.update(new_config)
    serialized = json.dumps(merged, indent=2)
    tmp_path = CONFIG_FILE.with_suffix(".tmp")
    try:
        tmp_path.write_text(serialized, encoding="utf-8")
        tmp_path.replace(CONFIG_FILE)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
    reload_config()


def get_config() -> dict:
    """Return a copy of the current config dict."""
    return copy.deepcopy(_config)


def _mask_key(value: str | None) -> str | None:
    """Mask an API key, showing first 4 and last 4 chars."""
    if not value:
        return value
    if len(value) <= 8:
        return "****"
    return value[:4] + "*" * (len(value) - 8) + value[-4:]


def _mask_key_map(mapping: dict | None) -> dict | None:
    """Mask every value in a dict of API keys."""
    if not mapping:
        return mapping
    return {k: _mask_key(v) for k, v in mapping.items()}


def get_config_masked() -> dict:
    """Return config with API keys masked (first 4 + last 4 visible)."""
    cfg = get_config()
    cfg["openrouter_api_key"] = _mask_key(cfg.get("openrouter_api_key"))
    cfg["azure_foundry_api_key"] = _mask_key(cfg.get("azure_foundry_api_key"))
    cfg["azure_foundry_api_key_map"] = _mask_key_map(cfg.get("azure_foundry_api_key_map"))
    cfg["azure_foundry_algorithm_api_key_map"] = _mask_key_map(
        cfg.get("azure_foundry_algorithm_api_key_map")
    )
    return cfg


# ---------------------------------------------------------------------------
# Initialise on import
# ---------------------------------------------------------------------------
reload_config()

# ---------------------------------------------------------------------------
# Backward compatibility: allow `from .config import COUNCIL_MODELS` etc.
# ---------------------------------------------------------------------------
_ATTR_TO_KEY = {
    "LLM_PROVIDER": "llm_provider",
    "OPENROUTER_API_KEY": "openrouter_api_key",
    "OPENROUTER_API_URL": "openrouter_api_url",
    "AZURE_FOUNDRY_ENDPOINT": "azure_foundry_endpoint",
    "AZURE_FOUNDRY_API_KEY": "azure_foundry_api_key",
    "AZURE_FOUNDRY_API_VERSION": "azure_foundry_api_version",
    "AZURE_FOUNDRY_DEPLOYMENT_MAP": "azure_foundry_deployment_map",
    "AZURE_FOUNDRY_ENDPOINT_MAP": "azure_foundry_endpoint_map",
    "AZURE_FOUNDRY_API_KEY_MAP": "azure_foundry_api_key_map",
    "AZURE_FOUNDRY_ALGORITHM_ENDPOINT_MAP": "azure_foundry_algorithm_endpoint_map",
    "AZURE_FOUNDRY_ALGORITHM_API_KEY_MAP": "azure_foundry_algorithm_api_key_map",
    "COUNCIL_MODELS": "council_models",
    "CHAIRMAN_MODEL": "chairman_model",
    "COUNCIL_ALGORITHM": "council_algorithm",
    "RANK_AGGREGATION_METHOD": "rank_aggregation_method",
}


def __getattr__(name: str):
    key = _ATTR_TO_KEY.get(name)
    if key is not None:
        return _config.get(key)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
