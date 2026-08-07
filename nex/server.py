"""
OpenAI-compatible server for Nex (multi-model OptiQ + MTP).

Usage:
    nex serve
    nex serve --port 8000 --model qwen3.5-9b --enable-mtp

Provides:
- POST /v1/chat/completions (streaming + non-streaming)
- GET /v1/models
- GET /health

Fully reuses the existing Engine, registry, MTP support, and chat templating.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Any, AsyncGenerator, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .models import get_default_model, get_profile, list_profiles

if TYPE_CHECKING:
    from .engine import Engine

app = FastAPI(
    title="MLX-SAGE · Nex Local Server",
    description=(
        "OpenAI-compatible local API for Apple Silicon MLX / OptiQ models (MTP optional). "
        "Part of MLX-SAGE (Sage-first product; Nex multi-model substrate). "
        "Local trust only — no auth; do not expose to untrusted networks."
    ),
    version="0.3.0",
)


# ---------------- Pydantic Models (OpenAI compatible) ----------------

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: Optional[str] = None
    messages: List[ChatMessage]
    temperature: float = 0.7
    top_p: float = 0.95
    max_tokens: int = 1024
    stream: bool = False
    # Nex/MTP extensions (passed through)
    enable_mtp: bool = Field(False, alias="enable_mtp")
    draft_model: Optional[str] = None
    num_draft_tokens: int = 3


class Choice(BaseModel):
    index: int = 0
    message: Optional[ChatMessage] = None
    delta: Optional[Dict[str, str]] = None
    finish_reason: Optional[str] = None
    # OpenAI tool calling extension (populated dynamically)
    tool_calls: Optional[List[Dict[str, Any]]] = None


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[Choice]
    usage: Usage


# ---------------- Engine Cache (simple, model + mtp aware) ----------------
# Engine / mlx-lm loaded lazily so /health and /v1/models work without MLX installed.

_engines: Dict[str, Any] = {}


def _get_engine(req: ChatCompletionRequest) -> Any:
    from .engine import Engine

    model = req.model or get_default_model()
    profile = get_profile(model)
    model_id = profile.repo_id

    # Build a cache key that includes MTP settings
    mtp_key = ""
    if req.enable_mtp:
        draft = req.draft_model or (profile.mtp_repo_id if profile.supports_mtp else None)
        if draft:
            mtp_key = f":mtp:{draft}:{req.num_draft_tokens}"

    cache_key = f"{model_id}{mtp_key}"

    if cache_key not in _engines:
        draft = None
        if req.enable_mtp:
            draft = req.draft_model
            if not draft and profile.supports_mtp:
                draft = profile.mtp_repo_id

        _engines[cache_key] = Engine(
            model_id=model_id,
            draft_model_id=draft,
            num_draft_tokens=req.num_draft_tokens,
        )
        _engines[cache_key].load()

    return _engines[cache_key]


# ---------------- Helpers ----------------

def _build_prompt(engine: Any, messages: List[ChatMessage]) -> str:
    """Convert OpenAI messages to the model's chat template."""
    msgs = [{"role": m.role, "content": m.content} for m in messages]
    return engine.apply_chat_template(msgs, add_generation_prompt=True)


async def _stream_completion(
    engine: Any,
    prompt: str,
    req: ChatCompletionRequest,
) -> AsyncGenerator[str, None]:
    """Yield SSE chunks in OpenAI format."""
    created = int(time.time())
    completion_id = f"chatcmpl-{int(time.time() * 1000)}"

    # First chunk with role
    first_chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": engine.model_id,
        "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
    }
    yield f"data: {json.dumps(first_chunk)}\n\n"

    full_text = ""
    try:
        for chunk, stats in engine.stream_generate(
            prompt,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            top_p=req.top_p,
        ):
            if chunk:
                full_text += chunk
                delta_chunk = {
                    "id": completion_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": engine.model_id,
                    "choices": [{"index": 0, "delta": {"content": chunk}, "finish_reason": None}],
                }
                yield f"data: {json.dumps(delta_chunk)}\n\n"

        # Final chunk
        final_chunk = {
            "id": completion_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": engine.model_id,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(final_chunk)}\n\n"
        yield "data: [DONE]\n\n"

    except Exception as e:
        error_chunk = {"error": {"message": str(e)}}
        yield f"data: {json.dumps(error_chunk)}\n\n"


# ---------------- Routes ----------------

@app.get("/health")
async def health():
    return {"status": "ok", "models": len(list_profiles())}


@app.get("/v1/models")
async def list_models():
    profiles = list_profiles()
    data = []
    for p in profiles:
        data.append(
            {
                "id": p.repo_id,
                "object": "model",
                "created": int(time.time()),
                "owned_by": p.family,
                "nex": {
                    "name": p.name,
                    "family": p.family,
                    "size_class": p.size_class,
                    "supports_mtp": p.supports_mtp,
                    "aliases": p.aliases,
                },
            }
        )
    return {"object": "list", "data": data}


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatCompletionRequest):
    if not req.messages:
        raise HTTPException(status_code=400, detail="messages is required")

    engine = _get_engine(req)
    prompt = _build_prompt(engine, req.messages)

    created = int(time.time())
    completion_id = f"chatcmpl-{int(time.time() * 1000)}"
    model_name = engine.model_id

    if req.stream:
        return StreamingResponse(
            _stream_completion(engine, prompt, req),
            media_type="text/event-stream",
        )

    # Non-streaming
    try:
        text, stats = engine.generate_once(
            prompt,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            top_p=req.top_p,
        )

        # Polish: Detect custom tool call format and convert to OpenAI tool_calls
        tool_call = parse_tool_call(text)
        message_content = text.strip()
        tool_calls = None
        finish_reason = "stop"

        if tool_call and tool_call.get("name") in TOOLS:
            tool_calls = [{
                "id": f"call_{int(time.time())}",
                "type": "function",
                "function": {
                    "name": tool_call["name"],
                    "arguments": json.dumps(tool_call.get("arguments", {})),
                }
            }]
            message_content = None  # or keep the raw for transparency
            finish_reason = "tool_calls"

        response = ChatCompletionResponse(
            id=completion_id,
            created=created,
            model=model_name,
            choices=[
                Choice(
                    message=ChatMessage(
                        role="assistant",
                        content=message_content or "",
                    ),
                    finish_reason=finish_reason,
                )
            ],
            usage=Usage(
                prompt_tokens=getattr(stats, "prompt_tokens", 0),
                completion_tokens=getattr(stats, "generation_tokens", 0),
                total_tokens=getattr(stats, "prompt_tokens", 0) + getattr(stats, "generation_tokens", 0),
            ),
        )
        # Attach tool_calls if present (OpenAI style)
        if tool_calls:
            response.choices[0].message = ChatMessage(role="assistant", content=message_content or "")
            # Extend the model dynamically for tool_calls
            response.choices[0].__dict__["message"].tool_calls = tool_calls  # hack for pydantic
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# For direct running (optional)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("nex.server:app", host="0.0.0.0", port=8000, reload=False)
