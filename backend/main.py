"""FastAPI backend for the Campus Customs desk dashboard.

Run from HW 5/backend:
    ../.venv/bin/uvicorn main:app --reload --port 8000

Every shop fact goes through the campus-customs MCP server (same .mcp.json the agents use); this
file has no SQL of its own. The only file operation here is /api/reset, which copies the original
database over the working copy.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastmcp import Client  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import audit  # noqa: E402
from agents import load_mcp_config, run_team, ticket_message  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ORIGINAL_DB = ROOT / "data" / "campus_customs.db"
WORKING_DB = ROOT / "data" / "campus_customs_new.db"

# ---------- MCP connection shared by all routes ----------

mcp: Client | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global mcp
    mcp = Client(load_mcp_config())
    async with mcp:
        yield


async def call_tool(name: str, args: dict | None = None) -> Any:
    """Call a campus-customs MCP tool and return its structured result (lists come back unwrapped)."""
    result = await mcp.call_tool(name, args or {}, raise_on_error=False)
    if result.is_error:
        text = " ".join(getattr(c, "text", "") for c in result.content)
        raise HTTPException(502, f"MCP tool {name} failed: {text}")
    data = result.structured_content
    if isinstance(data, dict) and set(data) == {"result"}:
        return data["result"]
    return data


app = FastAPI(title="Campus Customs desk API", lifespan=lifespan)
# The React desk (`npm run dev` in frontend/) is served from the Vite origin and calls this API
# directly, so the browser needs CORS permission for that origin. Other local ports are allowed too
# in case Vite picks the next free port.
VITE_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=VITE_ORIGINS,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)

# ---------- agent runs (in memory; the audit trail is the permanent record) ----------


class RunInfo(BaseModel):
    run_id: str
    ticket_id: int
    status: Literal["running", "done", "failed"]
    started_at: str
    finished_at: str | None = None
    result: dict | None = None
    error: str | None = None


RUNS: dict[str, RunInfo] = {}
_tasks: set[asyncio.Task] = set()
_run_lock = asyncio.Lock()  # one team run at a time, so two runs never race on the same tickets


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _running() -> RunInfo | None:
    return next((r for r in RUNS.values() if r.status == "running"), None)


async def _run_ticket(info: RunInfo) -> None:
    async with _run_lock:
        try:
            result = await run_team(ticket_message(info.ticket_id), ticket_id=info.ticket_id, run_id=info.run_id)
            info.result = result.model_dump(mode="json")
            info.status = "done"
        except Exception as exc:  # noqa: BLE001 - the failure is shown on the board and in the audit trail
            info.error = f"{type(exc).__name__}: {exc}"
            info.status = "failed"
        finally:
            info.finished_at = _now()


# ---------- tickets ----------


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "running": _running() is not None}


def _finished_runs() -> dict[int, dict]:
    """Latest successful team run per ticket since the last database reset, from the audit trail."""
    trail = json.loads(audit.AUDIT_PATH.read_text()) if audit.AUDIT_PATH.exists() else []
    done: dict[int, dict] = {}
    for e in trail:
        if e.get("kind") == "database_reset":
            done.clear()
        elif e.get("kind") == "team_run_end" and e.get("status") == "ok" and e.get("ticket_id") is not None:
            done[e["ticket_id"]] = {"run_id": e["run_id"], "finished_at": e["ts"]}
    return done


@app.get("/api/tickets")
async def tickets() -> list[dict]:
    """All tickets for the board. `status` is the database status; `state` is the board's view:
    working (team is on it now), resolved (the team finished its run, or the ticket is closed in the
    database), or open. A resolved ticket can still have a payment waiting for a human."""
    rows = await call_tool("list_tickets")
    pending = await call_tool("list_approvals", {"status": "pending"})
    finished = _finished_runs()
    running = _running()
    out = []
    for t in rows:
        if running and running.ticket_id == t["id"]:
            state = "working"
        elif t["status"] == "resolved" or t["id"] in finished:
            state = "resolved"
        else:
            state = "open"
        out.append({
            **t,
            "state": state,
            "last_run": finished.get(t["id"]),
            "running_run_id": running.run_id if running and running.ticket_id == t["id"] else None,
            "pending_approvals": sum(1 for a in pending if a["ticket_id"] == t["id"]),
        })
    return out


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int) -> RunInfo:
    """Start the agent team on one ticket. Returns at once; poll /api/runs/{run_id} or /api/events."""
    detail = await call_tool("get_ticket", {"ticket_id": ticket_id})
    if not detail["found"]:
        raise HTTPException(404, detail["message"])
    busy = _running()
    if busy:
        raise HTTPException(409, f"Ticket {busy.ticket_id} is already being worked (run {busy.run_id}).")
    info = RunInfo(run_id=uuid.uuid4().hex[:12], ticket_id=ticket_id, status="running", started_at=_now())
    RUNS[info.run_id] = info
    task = asyncio.create_task(_run_ticket(info))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)
    return info


@app.get("/api/runs")
async def runs() -> list[RunInfo]:
    return sorted(RUNS.values(), key=lambda r: r.started_at, reverse=True)


@app.get("/api/runs/{run_id}")
async def run_status(run_id: str) -> RunInfo:
    if run_id not in RUNS:
        raise HTTPException(404, f"No run {run_id} since the server started; see /api/events for older runs.")
    return RUNS[run_id]


# ---------- agent events (from output/audit_trail.json) ----------


def _event(seq: int, e: dict, ticket_of: dict[str, int | None]) -> dict | None:
    """Turn one audit entry into a board event: who spoke, what they said, which tools they used."""
    kind = e.get("kind")
    base = {"seq": seq, "ts": e.get("ts"), "run_id": e.get("run_id"),
            "ticket_id": ticket_of.get(e.get("run_id")), "agent": e.get("agent"),
            "depth": e.get("depth"), "kind": kind, "said": None, "tools": [], "delegated_to": []}
    if kind == "model_response":
        texts = [p["content"] for p in e.get("parts", []) if p["type"] == "text"]
        calls = [p for p in e.get("parts", []) if p["type"] == "tool_call"]
        tools = [{"tool": c["tool"], "args": c["args"]} for c in calls
                 if c["tool"] not in {"ask_teammate", "final_result"}]
        delegated = [c["args"].get("teammate") for c in calls
                     if c["tool"] == "ask_teammate" and isinstance(c["args"], dict)]
        if not (texts or tools or delegated):
            return None  # the step that only returns the final answer; the 'final' event covers it
        return {**base, "said": "\n".join(texts) or None, "tools": tools, "delegated_to": delegated}
    if kind == "model_request":
        results = [{"tool": p["tool"], "result": p["content"]} for p in e.get("parts", [])
                   if p["type"] == "tool_result" and p["tool"] not in {"ask_teammate", "final_result"}]
        return {**base, "kind": "tool_results", "tools": results} if results else None
    if kind == "agent_start":
        return {**base, "said": e.get("prompt")}
    if kind == "final":
        out = e.get("output") or {}
        return {**base, "said": out.get("summary"), "output": out}
    if kind == "delegation_refused":
        return {**base, "said": f"Hand-off to {e.get('to_agent')} refused ({e.get('reason')})."}
    if kind == "error":
        return {**base, "said": e.get("error")}
    if kind in {"team_run_start", "team_run_end", "human_decision", "database_reset"}:
        return {**base, "said": e.get("message") or e.get("status") or e.get("result") or e.get("error"),
                "detail": {k: v for k, v in e.items() if k not in {"ts", "run_id", "kind"}}}
    return None


@app.get("/api/events")
async def events(
    limit: int = Query(50, ge=1, le=500),
    after: int = Query(-1, description="only events with seq greater than this (for polling)"),
    run_id: str | None = None,
    ticket_id: int | None = None,
) -> dict:
    """Recent agent events, oldest first. Poll with ?after=<last seq> to get only new ones."""
    trail = json.loads(audit.AUDIT_PATH.read_text()) if audit.AUDIT_PATH.exists() else []
    ticket_of = {e["run_id"]: e.get("ticket_id") for e in trail if e.get("kind") == "team_run_start"}
    out = []
    for seq, e in enumerate(trail):
        if seq <= after or (run_id and e.get("run_id") != run_id):
            continue
        ev = _event(seq, e, ticket_of)
        if ev is None or (ticket_id is not None and ev["ticket_id"] != ticket_id):
            continue
        out.append(ev)
    return {"last_seq": len(trail) - 1, "events": out[-limit:]}


# ---------- approvals: agents prepare, a human decides ----------


class Decision(BaseModel):
    decided_by: str = Field(min_length=1, description="Name of the person clicking the button")
    note: str = ""


@app.get("/api/approvals")
async def approvals(status: Literal["pending", "approved", "rejected", "all"] = "pending") -> list[dict]:
    """Prepared requests, each with a `payee` name looked up from the database for the board."""
    rows = await call_tool("list_approvals", {"status": None if status == "all" else status})
    if not rows:
        return rows
    vendors = {v["id"]: v["name"] for v in await call_tool("list_vendors")}
    landlords = {l["id"]: l["landlord"] for l in (await call_tool("get_cash_and_bills"))["leases"]}
    for r in rows:
        r["payee"] = landlords.get(r["ref_id"]) if r["kind"] == "rent" else vendors.get(r["vendor_id"])
    return rows


async def _decide(approval_id: int, decision: str, body: Decision) -> dict:
    result = await call_tool("decide_approval", {
        "approval_id": approval_id, "decision": decision, "decided_by": body.decided_by, "note": body.note,
    })
    audit.append({"kind": "human_decision", "approval_id": approval_id, "decision": decision,
                  "decided_by": body.decided_by, "ok": result["ok"], "result": result["message"]})
    if not result["ok"]:
        raise HTTPException(409, result["message"])
    cash = await checking()
    return {**result, "checking": cash}


@app.post("/api/approvals/{approval_id}/approve")
async def approve(approval_id: int, body: Decision) -> dict:
    """The ONLY route that moves money: pays the prepared bill or places the prepared restock order."""
    return await _decide(approval_id, "approve", body)


@app.post("/api/approvals/{approval_id}/reject")
async def reject(approval_id: int, body: Decision) -> dict:
    return await _decide(approval_id, "reject", body)


# ---------- cash ----------


@app.get("/api/cash")
async def checking() -> dict:
    """Current checking balance from cash_accounts."""
    data = await call_tool("get_cash_and_bills")
    acct = next((a for a in data["cash_accounts"] if a["name"] == "checking"), None)
    if acct is None:
        raise HTTPException(404, "No checking account in cash_accounts.")
    return {"account": "checking", "balance": acct["balance"], "as_of": acct["as_of"], "today": data["today"]}


# ---------- reset ----------


@app.post("/api/reset")
async def reset() -> dict:
    """Copy data/campus_customs.db over the working copy so the next run starts fresh.
    The audit trail is kept (it is append-only); a reset entry marks the boundary."""
    busy = _running()
    if busy:
        raise HTTPException(409, f"Wait for run {busy.run_id} on ticket {busy.ticket_id} to finish first.")
    shutil.copyfile(ORIGINAL_DB, WORKING_DB)
    RUNS.clear()
    audit.append({"kind": "database_reset", "message": f"{WORKING_DB.name} restored from {ORIGINAL_DB.name}"})
    return {"ok": True, "tickets": await tickets(), "checking": await checking()}
