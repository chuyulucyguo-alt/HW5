"""Data types shared by the Campus Customs agent team."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
TicketStatus = Literal["open", "in_progress", "waiting_on_approval", "resolved"]


# ---------- run state passed to every agent ----------


class DelegationEvent(BaseModel):
    """One hand-off between agents, kept so a human can see who asked whom."""

    depth: int
    from_agent: AgentName
    to_agent: AgentName
    request: str
    result_summary: str | None = None
    refused: str | None = None  # set when the hand-off was blocked (self-call, loop, too deep)


@dataclass
class TeamDeps:
    """Passed through every run. `chain` is the path of agents currently waiting on each other."""

    run_id: str = ""
    chain: list[AgentName] = field(default_factory=list)
    trace: list[DelegationEvent] = field(default_factory=list)
    max_depth: int = 3


# ---------- what a specialist hands back ----------


class Fact(BaseModel):
    """A number or status the agent read from the database, with the tool it came from."""

    statement: str = Field(description="e.g. 'CC-TEE-WHITE size S has 0 on hand'")
    source_tool: str = Field(description="MCP tool that returned it, e.g. 'check_stock_and_price'")


class ProposedAction(BaseModel):
    """Something that should happen but has not happened yet."""

    action: str = Field(description="Plain-language action, e.g. 'Pay invoice 501 ($840) to Bulldog Print Co'")
    owner: AgentName
    tool: str | None = Field(default=None, description="MCP tool that would carry it out, if any")
    needs_human_approval: bool
    reason: str


class AgentReport(BaseModel):
    """What Inventory, Accounting, Facilities, or Customer Service returns."""

    agent: AgentName
    ticket_ids: list[int] = Field(default_factory=list)
    summary: str = Field(description="Two to four sentences answering the request")
    facts: list[Fact] = Field(default_factory=list)
    actions_taken: list[str] = Field(
        default_factory=list, description="Database changes already made, each with the tool's message"
    )
    proposed_actions: list[ProposedAction] = Field(default_factory=list)
    customer_message: str | None = Field(
        default=None, description="Draft reply to the requester, only for customer-facing work"
    )
    questions_for_human: list[str] = Field(default_factory=list)


# ---------- what the Boss hands back to the human ----------


class TicketPlan(BaseModel):
    ticket_id: int
    owner: AgentName = Field(description="Specialist responsible for this ticket")
    consulted: list[AgentName] = Field(default_factory=list)
    finding: str = Field(description="What the team found, with real numbers")
    plan: str = Field(description="Next steps in order")
    recommended_status: TicketStatus
    needs_human_approval: bool
    approval_request: str | None = Field(
        default=None, description="Exactly what the human must say yes or no to, with amounts"
    )


class BossBrief(BaseModel):
    """The Boss's answer to the shop owner."""

    summary: str
    tickets: list[TicketPlan] = Field(default_factory=list)
    cash_position: str | None = Field(
        default=None, description="Cash on hand, total owed, and what is left, if money is involved"
    )
    approvals_needed: list[str] = Field(default_factory=list)
    actions_taken: list[str] = Field(default_factory=list)


class TeamResult(BaseModel):
    """Returned by run_team: the entry agent's answer plus the delegation trail."""

    run_id: str
    entry_agent: AgentName
    output: BossBrief | AgentReport
    delegations: list[DelegationEvent]
    requests_used: int
    tool_calls_used: int
