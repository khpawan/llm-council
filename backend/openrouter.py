"""LLM API client with provider support (OpenRouter + Azure Foundry)."""

from typing import List, Dict, Any, Optional
import contextvars
import httpx

from .config import get_config

_CURRENT_ALGORITHM: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "llm_council_current_algorithm", default=None
)


def set_execution_algorithm(algorithm: Optional[str]) -> contextvars.Token:
    """Set current algorithm context for endpoint/key routing; returns reset token."""
    return _CURRENT_ALGORITHM.set((algorithm or "").strip().lower() or None)


def reset_execution_algorithm(token: contextvars.Token) -> None:
    _CURRENT_ALGORITHM.reset(token)


def _resolve_azure_deployment(model: str, cfg: Dict[str, Any]) -> str:
    deployment_map = cfg.get("azure_foundry_deployment_map") or {}
    return deployment_map.get(model, model)


def _resolve_azure_endpoint_and_key(
    model: str,
    cfg: Dict[str, Any],
) -> tuple[str, Optional[str]]:
    # Precedence: model-specific > algorithm-specific > global default
    endpoint_map = cfg.get("azure_foundry_endpoint_map") or {}
    api_key_map = cfg.get("azure_foundry_api_key_map") or {}
    algorithm_endpoint_map = cfg.get("azure_foundry_algorithm_endpoint_map") or {}
    algorithm_api_key_map = cfg.get("azure_foundry_algorithm_api_key_map") or {}

    model_endpoint = endpoint_map.get(model, "").rstrip("/")
    model_key = api_key_map.get(model)
    if model_endpoint:
        return model_endpoint, model_key or cfg.get("azure_foundry_api_key")

    algorithm = _CURRENT_ALGORITHM.get()
    if algorithm:
        algo_endpoint = algorithm_endpoint_map.get(algorithm, "").rstrip("/")
        if algo_endpoint:
            algo_key = algorithm_api_key_map.get(algorithm)
            return algo_endpoint, algo_key or cfg.get("azure_foundry_api_key")

    return (cfg.get("azure_foundry_endpoint") or "").rstrip("/"), cfg.get("azure_foundry_api_key")


def _build_request(
    model: str,
    messages: List[Dict[str, str]],
    config_override: Optional[Dict[str, Any]] = None,
) -> tuple[str, Dict[str, str], Dict[str, Any]]:
    cfg = config_override or get_config()
    provider = (cfg.get("llm_provider") or "openrouter").strip().lower()

    if provider == "azure_foundry":
        deployment = _resolve_azure_deployment(model, cfg)
        endpoint, api_key = _resolve_azure_endpoint_and_key(model, cfg)

        if not endpoint or not api_key:
            raise ValueError(
                "Azure Foundry routing missing endpoint/key. Set AZURE_FOUNDRY_ENDPOINT + AZURE_FOUNDRY_API_KEY or endpoint/key maps."
            )

        api_version = cfg.get("azure_foundry_api_version") or "2024-10-21"
        url = (
            f"{endpoint}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={api_version}"
        )
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "messages": messages,
        }
        return url, headers, payload

    # default: openrouter
    openrouter_api_key = cfg["openrouter_api_key"]
    if not openrouter_api_key:
        raise ValueError("OPENROUTER_API_KEY is required for LLM_PROVIDER=openrouter")

    headers = {
        "Authorization": f"Bearer {openrouter_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
    }
    openrouter_api_url = cfg.get("openrouter_api_url") or "https://openrouter.ai/api/v1/chat/completions"
    return openrouter_api_url, headers, payload


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0,
    config_override: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Query a single model via configured provider."""
    cfg = config_override or get_config()
    provider = (cfg.get("llm_provider") or "openrouter").strip().lower()

    try:
        url, headers, payload = _build_request(model, messages, config_override=cfg)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()

        data = response.json()
        message = data["choices"][0]["message"]

        return {
            "content": message.get("content"),
            "reasoning_details": message.get("reasoning_details"),
        }

    except Exception as e:
        print(f"Error querying model {model} via {provider}: {e}")
        return None


async def query_models_parallel(
    models: List[str],
    messages: List[Dict[str, str]]
) -> Dict[str, Optional[Dict[str, Any]]]:
    """Query multiple models in parallel."""
    import asyncio

    tasks = [query_model(model, messages) for model in models]
    responses = await asyncio.gather(*tasks)
    return {model: response for model, response in zip(models, responses)}
