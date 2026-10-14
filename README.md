# Campus Customs: AI agent front desk (HW 5)

Five PydanticAI agents (Boss, Inventory, Accounting, Facilities, Customer Service) work the Campus Customs shop tickets. They read and change the shop's SQLite database **only** through a FastMCP server. A FastAPI backend runs them, and a React "front desk" dashboard lets a person watch them work and sign any payment they prepare.

## Quick start

You need Python 3.12+, Node 20+, and a Portkey API key. Every agent uses `gpt-6-luna` through Portkey.

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate && pip install -r requirements.txt
```

```bash
cp .env.example .env
```

Put your `PORTKEY_API_KEY` in `.env`. Then start the backend (it launches the MCP server itself from `.mcp.json`):

```bash
cd backend && uvicorn main:app --reload --port 8000
```

In a second terminal, start the dashboard and open http://localhost:5173:

```bash
cd frontend && npm install && npm run dev
```

On the board: pick a ticket → **Send to the team →** → watch the desks → sign or void the checks under **Needs your signature**. **↺ Fresh day** resets the working database to the original.

## Layout

| Path | What it is |
|---|---|
| `AI_prompts.md` | Log of the prompts I gave my vibe coder, per problem |
| `requirements.txt`, `.env.example`, `.gitignore` | Python deps, key template, ignored files (`.env`, `.venv`, `node_modules`) |
| `.mcp.json` | Registers the `campus-customs` MCP server (stdio, paths relative to this folder) for Claude Code and for the backend |
| `data/campus_customs.db` | Original database (never modified) |
| `data/campus_customs_new.db` | Working copy the agents and the board change |
| `mcp_server/server.py`, `README.md` | FastMCP server with 13 tools; agents can only *prepare* payments, and only a human approval moves money |
| `backend/main.py` | FastAPI routes the dashboard calls (tickets, run, events, approvals, cash, reset) |
| `backend/models.py` | Pydantic/dataclass types: agent reports, Boss brief, delegation trail |
| `backend/prompts/*.md` | One detailed system prompt per agent: `boss`, `inventory`, `accounting`, `facilities`, `customer_service` |
| `backend/agents.py`, `audit.py`, `run_team.py` | Agent team + `ask_teammate` delegation loop, append-only audit trail, CLI runner |
| `frontend/` | React + Vite + TypeScript desk (corkboard tickets, agent desks, cash drawer, signature tray) |
| `output/harness.md` | Full harness: tables, MCP tools, agents, routes, dashboard, safety |
| `output/mcp_smoke.json` | Evidence of each MCP tool called from the vibe coder |
| `output/desk_tickets.html` | Expected vs. Actual per ticket, the Cash ledger, and the Reflection |
| `output/design.md` | Why the dashboard looks and works the way it does |
| `output/resolved_tickets.json` | Per ticket: final status, outcome, each agent's contribution, human approvals |
| `output/resolved_board.html` | Screenshots of the board for each resolved ticket (images embedded) |
| `output/audit_trail.json` | Every agent-loop step, hand-off, tool call, and human decision (append-only) |
| `output/github_url.txt` | Link to this repository |

## Result of the final run

Starting checking **$3,400.00** → rent ($2,400, ticket 102) and invoice 501 ($840, ticket 101) signed by a human → **$160.00**, which matches `cash_accounts` in `data/campus_customs_new.db`. The $264 hoodie restock for ticket 103 is held for lack of cash. Details are on the Cash tab of `output/desk_tickets.html`.
