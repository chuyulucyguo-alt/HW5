# Campus Customs: AI agent front desk (HW 5)

Five PydanticAI agents (Boss, Inventory, Accounting, Facilities, Customer Service) work the Campus Customs shop tickets. They read and change the shop's SQLite database **only** through a FastMCP server. A FastAPI backend runs them, and a React "front desk" dashboard lets a person watch them work and sign any payment they prepare.

## Setup (once)

You need Python 3.12+, Node 20+, and a Portkey API key. Every agent uses `gpt-6-luna` through Portkey. Run these from the project root:

```bash
python3 -m venv .venv
```

```bash
source .venv/bin/activate && pip install -r requirements.txt
```

```bash
cp .env.example .env
```

Open `.env` and put your key after `PORTKEY_API_KEY=`.

## How to run it

### 1. Copy the original database to the working copy (when you need a clean run)

`data/campus_customs.db` is the original and is never changed. The agents and the board only change the working copy, `data/campus_customs_new.db`. To start from clean data, copy the original over it:

```bash
cp data/campus_customs.db data/campus_customs_new.db
```

The repo ships the working copy in its **final graded state** (all three tickets worked, checking at $160). Skip this step if you want to look at that state first.

### 2. Start the MCP server

The server is `mcp_server/server.py` (FastMCP, stdio, 13 tools over `data/campus_customs_new.db`). It's registered in `.mcp.json` as `campus-customs`, so:

- **Claude Code** starts it automatically when you open this folder. Approve the `campus-customs` server once when asked.
- **The FastAPI backend** (step 3) starts its own copy from the same `.mcp.json`, so you don't need a separate terminal for the app.
- **To run it by hand** (e.g. to test it), from the project root with the venv active:

```bash
python mcp_server/server.py
```

It waits for an MCP client on stdin/stdout. Press Ctrl+C to stop it.

### 3. Start the FastAPI backend

In a terminal with the venv active:

```bash
cd backend && uvicorn main:app --reload --port 8000
```

The API is now at http://localhost:8000, and you can check it at http://localhost:8000/api/health. Every route is listed in `output/harness.md`.

### 4. Start the React board

In a second terminal:

```bash
cd frontend && npm install && npm run dev
```

Open http://localhost:5173. The board calls the backend at `http://localhost:8000` (set in `frontend/.env`), and the backend allows that origin through CORS.

### 5. Reset the database before a full three-ticket run

Always start a full run of tickets 101, 102 and 103 from clean data. Click **↺ Fresh day** in the board's top bar, which copies the original database over the working copy and keeps the audit trail. Or do the same from a terminal while the backend is running:

```bash
curl -X POST http://localhost:8000/api/reset
```

Checking should read **$3,400.00** afterward. Then, on the board:

1. Send each ticket to the team one at a time (**Send to the team →**). Wait for its RESOLVED stamp before starting the next; the backend runs one ticket at a time.
2. Watch the desks, the desk log, and the "who did what" report.
3. In **Needs your signature**, type your name and **Sign & pay**, **Sign & order**, or **Void** each check. Only a signature moves money, and the cash drawer drops when you sign.

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
