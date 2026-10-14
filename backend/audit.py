"""Append-only audit trail for the agent team: output/audit_trail.json.

The file is one JSON array. Every agent-loop step adds one entry; nothing is ever removed, so runs
accumulate. Each write goes to a temp file and replaces the original, so a crash mid-write can't
leave half a file behind.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)

AUDIT_PATH = Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"
MAX_CHARS = 6000  # cap very long tool results so the trail stays readable


def _clip(value: Any) -> Any:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    if len(text) <= MAX_CHARS:
        return value
    return text[:MAX_CHARS] + f"... [clipped {len(text) - MAX_CHARS} chars]"


def _usage(usage) -> dict:
    return {
        "requests": usage.requests,
        "tool_calls": usage.tool_calls,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
    }


def describe_request(req: ModelRequest) -> dict:
    """What went INTO the model on this step: the user/delegated prompt, tool results, retry notes."""
    parts = []
    for p in req.parts:
        if isinstance(p, UserPromptPart):
            parts.append({"type": "prompt", "content": _clip(p.content)})
        elif isinstance(p, ToolReturnPart):
            parts.append({"type": "tool_result", "tool": p.tool_name, "call_id": p.tool_call_id,
                          "content": _clip(p.content)})
        elif isinstance(p, RetryPromptPart):
            parts.append({"type": "retry", "tool": p.tool_name, "content": _clip(p.model_response())})
    return {"parts": parts}


def describe_response(resp: ModelResponse) -> dict:
    """What came OUT of the model on this step: text and the tool calls it decided to make."""
    parts = []
    for p in resp.parts:
        if isinstance(p, ToolCallPart):
            parts.append({"type": "tool_call", "tool": p.tool_name, "call_id": p.tool_call_id,
                          "args": _clip(p.args_as_dict())})
        elif isinstance(p, TextPart) and p.content.strip():
            parts.append({"type": "text", "content": _clip(p.content)})
    return {"model": resp.model_name, "finish_reason": resp.finish_reason, "parts": parts}


def append(entry: dict) -> None:
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    trail: list = []
    if AUDIT_PATH.exists() and AUDIT_PATH.stat().st_size:
        try:
            trail = json.loads(AUDIT_PATH.read_text())
        except json.JSONDecodeError:
            # never destroy history: keep the unreadable file and start a fresh array beside it
            AUDIT_PATH.rename(AUDIT_PATH.with_suffix(f".corrupt-{datetime.now():%Y%m%d%H%M%S}.json"))
    trail.append({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry})
    tmp = AUDIT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(trail, indent=2, default=str) + "\n")
    os.replace(tmp, AUDIT_PATH)


def step(run_id: str, agent: str, chain: list[str], step_no: int, kind: str, usage, **detail) -> None:
    append({
        "run_id": run_id,
        "agent": agent,
        "chain": chain,
        "depth": len(chain) - 1,
        "step": step_no,
        "kind": kind,
        "usage_so_far": _usage(usage),
        **detail,
    })
