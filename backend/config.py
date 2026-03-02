"""Configuration for the LLM Council."""

import json
import os
from dotenv import load_dotenv

load_dotenv()


def _json_map(env_name: str) -> dict:
    raw = os.getenv(env_name, "{}")
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


# Provider selection: "openrouter" (default) or "azure_foundry"
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter").strip().lower()

# OpenRouter config
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")

# Azure Foundry (Azure OpenAI-compatible chat completions) config
AZURE_FOUNDRY_ENDPOINT = os.getenv("AZURE_FOUNDRY_ENDPOINT", "").rstrip("/")
AZURE_FOUNDRY_API_KEY = os.getenv("AZURE_FOUNDRY_API_KEY")
AZURE_FOUNDRY_API_VERSION = os.getenv("AZURE_FOUNDRY_API_VERSION", "2024-10-21")

# Optional map of model aliases to Azure deployment names.
# Example: {"council-1":"gpt-4.1", "chairman":"gpt-4.1"}
AZURE_FOUNDRY_DEPLOYMENT_MAP = _json_map("AZURE_FOUNDRY_DEPLOYMENT_MAP")

# Optional model-level endpoint/key routing maps.
# Example: {"gpt-5.2":"https://<resource>.services.ai.azure.com/api/projects/<proj>"}
AZURE_FOUNDRY_ENDPOINT_MAP = _json_map("AZURE_FOUNDRY_ENDPOINT_MAP")
AZURE_FOUNDRY_API_KEY_MAP = _json_map("AZURE_FOUNDRY_API_KEY_MAP")

# Optional algorithm-level endpoint/key routing maps.
# Example: {"red_team":"https://.../api/projects/project-b"}
AZURE_FOUNDRY_ALGORITHM_ENDPOINT_MAP = _json_map("AZURE_FOUNDRY_ALGORITHM_ENDPOINT_MAP")
AZURE_FOUNDRY_ALGORITHM_API_KEY_MAP = _json_map("AZURE_FOUNDRY_ALGORITHM_API_KEY_MAP")

# Council members - model identifiers (OpenRouter model IDs by default).
# For Azure Foundry, these can be deployment names (or aliases mapped in AZURE_FOUNDRY_DEPLOYMENT_MAP).
COUNCIL_MODELS = [
    m.strip()
    for m in os.getenv(
        "COUNCIL_MODELS",
        "openai/gpt-5.1,google/gemini-3-pro-preview,anthropic/claude-sonnet-4.5,x-ai/grok-4",
    ).split(",")
    if m.strip()
]

# Chairman model - synthesizes final response
CHAIRMAN_MODEL = os.getenv("CHAIRMAN_MODEL", "google/gemini-3-pro-preview")

# Council algorithm options:
# - peer_review (default): Stage1 + Stage2 + Stage3
# - consensus_only: Stage1 + Stage3 (skip Stage2)
# - chairman_only: chairman answers directly
# - red_team / audience_split / claim_evidence: custom stage2 reviewer modes
COUNCIL_ALGORITHM = os.getenv("COUNCIL_ALGORITHM", "peer_review").strip().lower()

# Aggregate ranking method for Stage2 metadata: average_rank | borda
RANK_AGGREGATION_METHOD = os.getenv("RANK_AGGREGATION_METHOD", "average_rank").strip().lower()

# Data directory for conversation storage
DATA_DIR = "data/conversations"
