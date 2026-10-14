"""The Campus Customs agent team: Boss, Inventory, Accounting, Facilities, Customer Service.

Every agent:
  - runs on gpt-6-luna through Portkey,
  - reads its system prompt from prompts/<role>.md (re-read on every run, so edits apply immediately),
  - gets only its own slice of the campus-customs MCP tools (ROLE_TOOLS),
  - can hand work to ANY other agent with `ask_teammate` (full connectivity).

Delegation is a nested agent run that shares the caller's usage budget. A hand-off is refused if it
targets the caller itself, an agent already waiting further up the chain (that would be a loop), or
goes deeper than TeamDeps.max_depth. Each refusal is returned to the model as text so it can adjust.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import get_args

from dotenv import load_dotenv
from fastmcp import Client
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RunUsage, UsageLimits

import audit

from models import AgentName, AgentReport, BossBrief, DelegationEvent, TeamDeps, TeamResult

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent  # HW 5/
PROMPTS = HERE / "prompts"
MCP_CONFIG = ROOT / ".mcp.json"

load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")

MODEL_NAME = "gpt-6-luna"  # the only model this homework allows
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"
# Token/cost guardrails for one team run (all five agents together share these).
LIMITS = UsageLimits(request_limit=40, tool_calls_limit=60, total_tokens_limit=400_000)
MODEL_SETTINGS = ModelSettings(timeout=90, max_tokens=4000)  # per model call
TEAM_TIMEOUT_S = 600  # whole team run

ROLES: tuple[AgentName, ...] = get_args(AgentName)

ROLE_DESCRIPTIONS: dict[AgentName, str] = {
    "boss": "triages tickets, assigns owners, checks the whole cash picture, briefs the owner",
    "inventory": "stock on hand by size, shortfalls, vendor lead times, restock dates, prepares restock orders",
    "accounting": "cash, invoices, prepares payments for owner approval, bulk quotes and discount rules",
    "facilities": "the Chapel Street lease, landlord, rent due dates, the physical shop",
    "customer_service": "customer orders and price requests, drafts replies to customers",
}

# Which MCP tools each role may call. ask_teammate is added to every role on top of these.
# No agent gets decide_approval or list_tickets: approving money is the human's job via the dashboard API.
ROLE_TOOLS: dict[AgentName, set[str]] = {
    "boss": {"list_open_tickets", "get_ticket", "get_cash_and_bills", "update_ticket", "list_approvals"},
    "inventory": {"get_ticket", "check_stock_and_price", "list_vendors", "adjust_inventory", "prepare_purchase"},
    "accounting": {
        "get_ticket", "get_cash_and_bills", "quote_bulk_price", "list_vendors", "prepare_payment", "list_approvals",
    },
    "facilities": {"get_ticket", "get_cash_and_bills", "list_vendors"},
    "customer_service": {
        "list_open_tickets", "get_ticket", "check_stock_and_price", "quote_bulk_price", "update_ticket",
    },
}


# ---------- model and MCP connection ----------


def make_model() -> OpenAIResponsesModel:
    api_key = os.getenv("PORTKEY_API_KEY")
    if not api_key:
        raise RuntimeError("PORTKEY_API_KEY is missing; put it in HW 5/.env or the parent .env")
    client = AsyncOpenAI(
        api_key=api_key,
        base_url=PORTKEY_BASE_URL,
        default_headers={"x-portkey-api-key": api_key},
    )
    # gpt-6-luna only allows function tools on the Responses API, not chat completions.
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def load_mcp_config(db_path: Path | None = None) -> dict:
    """Read .mcp.json (the same file Claude Code uses) and make it runnable from any working folder.

    Paths in .mcp.json are relative to the project root, so they are resolved against ROOT here.
    If the configured interpreter is missing (e.g. a differently named venv), the Python running
    this backend is used instead, since it already has fastmcp installed.
    """
    config = json.loads(MCP_CONFIG.read_text())
    server = config["mcpServers"]["campus-customs"]
    command = Path(server["command"])
    if not command.is_absolute():
        command = ROOT / command
    server["command"] = str(command) if command.exists() else sys.executable
    server["args"] = [str(ROOT / a) if a.endswith(".py") and not Path(a).is_absolute() else a for a in server["args"]]
    server["cwd"] = str(ROOT)
    if db_path is not None:
        server["env"] = {**server.get("env", {}), "CAMPUS_CUSTOMS_DB": str(Path(db_path).resolve())}
    return config


def make_toolset(db_path: Path | None = None) -> MCPToolset:
    """Start the campus-customs server exactly as .mcp.json says. db_path points it at another DB copy."""
    return MCPToolset(Client(load_mcp_config(db_path)))


# ---------- delegation ----------


async def ask_teammate(ctx: RunContext[TeamDeps], teammate: AgentName, request: str) -> str:
    """Hand a specific question or task to another agent and get their report back.

    teammate: one of boss, inventory, accounting, facilities, customer_service.
    request: a self-contained request with the ticket id, sku/size/qty or invoice/lease id, and the
    exact question. The teammate cannot see your conversation, only this text.
    """
    deps = ctx.deps
    me = deps.chain[-1]
    depth = len(deps.chain)
    event = DelegationEvent(depth=depth, from_agent=me, to_agent=teammate, request=request)
    deps.trace.append(event)

    if teammate == me:
        return _refuse(deps, event, "self", "Refused: you cannot delegate to yourself. "
                       "Do the work with your own tools.", ctx.usage)
    if teammate in deps.chain:
        path = " -> ".join(deps.chain)
        return _refuse(deps, event, "loop", f"Refused: {teammate} is already waiting on you (chain: "
                       f"{path}). Put this question in your report's questions_for_human or "
                       "proposed_actions and they will see it.", ctx.usage)
    if depth > deps.max_depth:
        return _refuse(deps, event, "too_deep", "Refused: the delegation chain is too deep. Answer "
                       "with what you have and note what is missing.", ctx.usage)

    sub_deps = TeamDeps(
        run_id=deps.run_id, chain=[*deps.chain, teammate], trace=deps.trace, max_depth=deps.max_depth
    )
    out = await run_agent_loop(
        teammate, f"Request from {me.replace('_', ' ')}:\n{request}", sub_deps, usage=ctx.usage
    )
    event.result_summary = out.summary
    return out.model_dump_json(exclude_defaults=True)


def _refuse(deps: TeamDeps, event: DelegationEvent, reason: str, message: str, usage) -> str:
    event.refused = reason
    audit.step(deps.run_id, event.from_agent, deps.chain, -1, "delegation_refused", usage,
               to_agent=event.to_agent, request=event.request, reason=reason)
    return message


# ---------- the audited agent loop ----------


async def run_agent_loop(role: AgentName, prompt: str, deps: TeamDeps, usage: RunUsage | None = None):
    """Run one agent step by step with agent.iter and write every step to output/audit_trail.json.

    Steps: 'model_request' (what the model was given: the prompt, tool results, retry notes),
    'model_response' (its text and the tool calls it chose), and 'final' (its typed output).
    `usage` is the caller's budget when this is a delegated run, so the team shares one limit.
    """
    agent = TEAM[role]
    step_no = 0
    audit.step(deps.run_id, role, deps.chain, step_no, "agent_start", usage or RunUsage(), prompt=prompt)
    try:
        async with agent.iter(prompt, deps=deps, usage=usage, usage_limits=LIMITS,
                              model_settings=MODEL_SETTINGS) as run:
            async for node in run:
                step_no += 1
                if Agent.is_model_request_node(node):
                    audit.step(deps.run_id, role, deps.chain, step_no, "model_request", run.usage,
                               **audit.describe_request(node.request))
                elif Agent.is_call_tools_node(node):
                    audit.step(deps.run_id, role, deps.chain, step_no, "model_response", run.usage,
                               **audit.describe_response(node.model_response))
        out = run.result.output
    except Exception as exc:
        audit.step(deps.run_id, role, deps.chain, step_no + 1, "error", usage or RunUsage(),
                   error=f"{type(exc).__name__}: {exc}")
        raise
    audit.step(deps.run_id, role, deps.chain, step_no + 1, "final", run.usage,
               output=out.model_dump(mode="json"))
    return out


# ---------- building the five agents ----------


def team_roster(role: AgentName, deps: TeamDeps) -> str:
    others = "\n".join(
        f"- `{name}`: {desc}" for name, desc in ROLE_DESCRIPTIONS.items() if name != role
    )
    chain = " -> ".join(deps.chain)
    blocked = [a for a in deps.chain if a != role]
    note = (
        f"Agents already waiting on this request (do not ask them): {', '.join(blocked)}."
        if blocked
        else "You are the first agent on this request."
    )
    return (
        f"## Your team\nYou are `{role}`. You can reach any teammate with `ask_teammate`:\n{others}\n\n"
        f"Current delegation chain: {chain}. {note}"
    )


def build_agent(role: AgentName, model: OpenAIResponsesModel, toolset: MCPToolset) -> Agent:
    allowed = ROLE_TOOLS[role]
    agent = Agent(
        model,
        name=role,
        deps_type=TeamDeps,
        output_type=BossBrief if role == "boss" else AgentReport,
        toolsets=[toolset.filtered(lambda ctx, tool_def: tool_def.name in allowed)],
        tools=[ask_teammate],
        retries=2,
    )

    @agent.instructions
    def role_prompt() -> str:
        return (PROMPTS / f"{role}.md").read_text(encoding="utf-8").strip()

    @agent.instructions
    def roster(ctx: RunContext[TeamDeps]) -> str:
        return team_roster(role, ctx.deps)

    if role != "boss":

        @agent.output_validator
        def stamp_role(out: AgentReport) -> AgentReport:
            out.agent = role
            return out

    return agent


TEAM: dict[AgentName, Agent] = {}


def build_team(db_path: Path | None = None) -> MCPToolset:
    """(Re)build all five agents on one shared MCP connection and return that connection."""
    model = make_model()
    toolset = make_toolset(db_path)
    TEAM.clear()
    for role in ROLES:
        TEAM[role] = build_agent(role, model, toolset)
    return toolset


# ---------- entry point ----------


def ticket_message(ticket_id: int) -> str:
    return (
        f"Work ticket {ticket_id} only. Find out what it needs, get the right teammates' answers, prepare any "
        "payment or restock order that should happen (I approve those on the dashboard), set the ticket's "
        "status, and brief me on what you need from me."
    )


async def run_team(message: str, entry: AgentName = "boss", db_path: Path | None = None,
                   ticket_id: int | None = None, run_id: str | None = None) -> TeamResult:
    """Send one message to the team, starting at `entry` (the Boss by default)."""
    toolset = build_team(db_path)
    deps = TeamDeps(run_id=run_id or uuid.uuid4().hex[:12], chain=[entry])
    usage = RunUsage()
    audit.append({"run_id": deps.run_id, "kind": "team_run_start", "entry_agent": entry, "ticket_id": ticket_id,
                  "message": message, "model": MODEL_NAME,
                  "database": str(db_path or "data/campus_customs_new.db"),
                  "limits": {"requests": LIMITS.request_limit, "tool_calls": LIMITS.tool_calls_limit,
                             "total_tokens": LIMITS.total_tokens_limit, "timeout_s": TEAM_TIMEOUT_S}})
    try:
        async with asyncio.timeout(TEAM_TIMEOUT_S), toolset:  # one MCP process for every nested run
            output = await run_agent_loop(entry, message, deps, usage=usage)
    except BaseException as exc:
        audit.append({"run_id": deps.run_id, "kind": "team_run_end", "status": "failed", "ticket_id": ticket_id,
                      "error": f"{type(exc).__name__}: {exc}", "usage": audit._usage(usage)})
        raise
    audit.append({"run_id": deps.run_id, "kind": "team_run_end", "status": "ok", "ticket_id": ticket_id,
                  "delegations": [d.model_dump() for d in deps.trace], "usage": audit._usage(usage)})
    return TeamResult(
        run_id=deps.run_id,
        entry_agent=entry,
        output=output,
        delegations=deps.trace,
        requests_used=usage.requests,
        tool_calls_used=usage.tool_calls,
    )
