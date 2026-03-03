"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Dict, Any
import uuid
import json
import asyncio

from . import storage
from .council import run_full_council, generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings
from .openrouter import set_execution_algorithm, reset_execution_algorithm, query_model
from .config import get_config_masked, save_config, reload_config, get_config

app = FastAPI(title="LLM Council API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str
    algorithm: str | None = Field(default=None, description="peer_review|consensus_only|chairman_only|red_team|audience_split|claim_evidence")


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Run the 3-stage council process
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content,
        algorithm=request.algorithm,
    )

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content)

            algo = request.algorithm
            token = set_execution_algorithm(algo)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Stage 1: Collect responses
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            if algo in ("chairman_only",):
                stage1_results = []
            else:
                stage1_results = await stage1_collect_responses(request.content)
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            stage2_results = []
            label_to_model = {}
            aggregate_rankings = []

            if algo not in ("chairman_only", "consensus_only"):
                # Stage 2: Collect rankings
                yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
                stage2_mode = "peer_review"
                if algo in ("red_team", "audience_split", "claim_evidence"):
                    stage2_mode = algo
                stage2_results, label_to_model = await stage2_collect_rankings(request.content, stage1_results, mode=stage2_mode)
                aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
                yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(request.content, stage1_results, stage2_results)
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


class SaveConfigRequest(BaseModel):
    """Request to save configuration."""
    llm_provider: str
    openrouter_api_key: str | None = None
    openrouter_api_url: str | None = None
    azure_foundry_endpoint: str | None = None
    azure_foundry_api_key: str | None = None
    azure_foundry_api_version: str | None = None
    azure_foundry_deployment_map: dict | None = None
    azure_foundry_endpoint_map: dict | None = None
    azure_foundry_api_key_map: dict | None = None
    azure_foundry_algorithm_endpoint_map: dict | None = None
    azure_foundry_algorithm_api_key_map: dict | None = None
    council_models: list[str]
    chairman_model: str
    council_algorithm: str
    rank_aggregation_method: str


@app.get("/api/config")
async def get_config_endpoint():
    """Return current configuration with API keys masked."""
    return get_config_masked()


@app.post("/api/config")
async def save_config_endpoint(request: SaveConfigRequest):
    """Save configuration. Preserves existing API keys if masked values are sent back."""
    config_data = request.model_dump()

    # Preserve existing API keys if the frontend sent back masked values
    existing = get_config()

    if config_data.get("openrouter_api_key") and "*" in config_data["openrouter_api_key"]:
        config_data["openrouter_api_key"] = existing.get("openrouter_api_key")

    if config_data.get("azure_foundry_api_key") and "*" in config_data["azure_foundry_api_key"]:
        config_data["azure_foundry_api_key"] = existing.get("azure_foundry_api_key")

    # Check values in azure_foundry_api_key_map
    if config_data.get("azure_foundry_api_key_map"):
        existing_map = existing.get("azure_foundry_api_key_map") or {}
        for key, value in config_data["azure_foundry_api_key_map"].items():
            if value and "*" in value:
                config_data["azure_foundry_api_key_map"][key] = existing_map.get(key)

    # Check values in azure_foundry_algorithm_api_key_map
    if config_data.get("azure_foundry_algorithm_api_key_map"):
        existing_map = existing.get("azure_foundry_algorithm_api_key_map") or {}
        for key, value in config_data["azure_foundry_algorithm_api_key_map"].items():
            if value and "*" in value:
                config_data["azure_foundry_algorithm_api_key_map"][key] = existing_map.get(key)

    save_config(config_data)
    reload_config()
    return {"status": "ok", "message": "Configuration saved and reloaded"}


@app.post("/api/config/test")
async def test_config_endpoint():
    """Test connectivity by pinging the first council model."""
    try:
        reload_config()
        config = get_config()
        council_models = config.get("council_models", [])
        if not council_models:
            raise HTTPException(status_code=400, detail="No council models configured")

        test_model = council_models[0]
        result = await query_model(
            test_model,
            "Say 'hello' in one word.",
            system_prompt="You are a helpful assistant."
        )

        if result is None:
            return {"status": "error", "message": f"Failed to get response from {test_model}"}

        return {
            "status": "ok",
            "model": test_model,
            "response": result.get("content", "")[:200]
        }
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
