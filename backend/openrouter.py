"""LLM API client with provider support (OpenRouter + Azure Foundry)."""

from typing import List, Dict, Any, Optional
import contextvars
import httpx

from .config import (
    LLM_PROVIDER,
    OPENROUTER_API_KEY,
    OPENROUTER_API_URL,
    AZURE_FOUNDRY_ENDPOINT,
    AZURE_FOUNDRY_API_KEY,
    AZURE_FOUNDRY_API_VERSION,
    AZURE_FOUNDRY_DEPLOYMENT_MAP,
    AZURE_FOUNDRY_ENDPOINT_MAP,
    AZURE_FOUNDRY_API_KEY_MAP,
    AZURE_FOUNDRY_ALGORITHM_ENDPOINT_MAP,
    AZURE_FOUNDRY_ALGORITHM_API_KEY_MAP,
)

_CURRENT_ALGORITHM: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "llm_council_current_algorithm", default=None
)


def set_execution_algorithm(algorithm: Optional[str]) -> contextvars.Token:
    """Set current algorithm context for endpoint/key routing; returns reset token."""
    return _CURRENT_ALGORITHM.set((algorithm or "").strip().lower() or None)


def reset_execution_algorithm(token: contextvars.Token) -> None:
    _CURRENT_ALGORITHM.reset(token)


def _resolve_azure_deployment(model: str) -> str:
    return AZURE_FOUNDRY_DEPLOYMENT_MAP.get(model, model)


def _resolve_azure_endpoint_and_key(model: str) -> tuple[str, Optional[str]]:
    # Precedence: model-specific > algorithm-specific > global default
    model_endpoint = AZURE_FOUNDRY_ENDPOINT_MAP.get(model, "").rstrip("/")
    model_key = AZURE_FOUNDRY_API_KEY_MAP.get(model)
    if model_endpoint:
        return model_endpoint, model_key or AZURE_FOUNDRY_API_KEY

    algorithm = _CURRENT_ALGORITHM.get()
    if algorithm:
        algo_endpoint = AZURE_FOUNDRY_ALGORITHM_ENDPOINT_MAP.get(algorithm, "").rstrip("/")
        if algo_endpoint:
            algo_key = AZURE_FOUNDRY_ALGORITHM_API_KEY_MAP.get(algorithm)
            return algo_endpoint, algo_key or AZURE_FOUNDRY_API_KEY

    return AZURE_FOUNDRY_ENDPOINT, AZURE_FOUNDRY_API_KEY


def _build_request(model: str, messages: List[Dict[str, str]]) -> tuple[str, Dict[str, str], Dict[str, Any]]:
    provider = LLM_PROVIDER

    if provider == "azure_foundry":
        deployment = _resolve_azure_deployment(model)
        endpoint, api_key = _resolve_azure_endpoint_and_key(model)

        if not endpoint or not api_key:
            raise ValueError(
                "Azure Foundry routing missing endpoint/key. Set AZURE_FOUNDRY_ENDPOINT + AZURE_FOUNDRY_API_KEY or endpoint/key maps."
            )

        url = (
            f"{endpoint}/openai/deployments/{deployment}/chat/completions"
            f"?api-version={AZURE_FOUNDRY_API_VERSION}"
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
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY is required for LLM_PROVIDER=openrouter")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
    }
    return OPENROUTER_API_URL, headers, payload


async def query_model(
    model: str,
    messages: List[Dict[str, str]],
    timeout: float = 120.0
) -> Optional[Dict[str, Any]]:
    """Query a single model via configured provider."""
    try:
        url, headers, payload = _build_request(model, messages)

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
        print(f"Error querying model {model} via {LLM_PROVIDER}: {e}")
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
