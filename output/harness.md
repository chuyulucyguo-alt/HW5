# Campus Customs Harness

A Campus Customs shop run by five PydanticAI agents. They reach the shop's SQLite database only through a FastMCP server, are driven by a FastAPI backend, and are watched and approved from a React front desk.

**Contents:** [Database](#database) · [MCP server and all 13 tools](#mcp-server) · [The five agents](#agent-team-pydanticai) · [Audit trail](#audit-trail-outputaudit_trailjson) · [Safety](#safety) · [Backend API routes](#backend-api-backendmainpy-fastapi) · [Dashboard](#dashboard-frontend-react--vite--typescript) · [Final run results](#final-run-results-problem-9)

**How to run everything**
1. `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt` at the project root (installs PydanticAI, FastMCP, FastAPI). Copy `.env.example` to `.env` and put in your `PORTKEY_API_KEY`.
2. Backend: `cd backend && uvicorn main:app --reload --port 8000`. It starts the MCP server itself from `.mcp.json`.
3. Board: `cd frontend && npm install && npm run dev`, then open http://localhost:5173.
4. ↺ Fresh day on the board (or `POST /api/reset`) restores the original database.

## Database

Source: `data/campus_customs.db` (original, read-only). Agents work on the copy `data/campus_customs_new.db`.

### Tables

| Table | Fields | Why it matters for the agents |
|---|---|---|
| `desk` | `date_today`, `notes` | Gives agents the shop's "today" (2026-08-31), so they can judge what's due or overdue. |
| `inventory` | `sku`, `name`, `size`, `qty`, `location` (key: `sku` + `size`) | Tells agents what's actually on the shelf by size, so they can say whether an order can be filled. |
| `pricing` | `sku`, `unit_cost`, `list_price` | Lets agents quote real prices and see the margin before agreeing to any discount. |
| `vendors` | `id`, `name`, `specialty`, `lead_days` | Shows who can restock which items and how long it takes, so agents can give realistic dates. |
| `leases` | `id`, `space_name`, `landlord`, `monthly_rent`, `next_due`, `notes` | Holds rent amounts and due dates, which agents need when they plan the shop's cash. |
| `cash_accounts` | `name`, `balance`, `date` | The money available; agents must check it before proposing any payment. |
| `payments` | `id`, `kind`, `ref_id`, `amount`, `account`, `paid_at`, `approved_by` | The record of money going out. `approved_by` means every payment needs someone to sign off on it. |
| `invoices` | `id`, `vendor_id` → `vendors.id`, `amount`, `due_date`, `status`, `description` | Bills the shop owes. Agents use these to decide what to pay and what is overdue. |
| `tickets` | `id`, `type`, `requester`, `subject`, `sku`, `size`, `qty`, `lease_id` → `leases.id`, `invoice_id` → `invoices.id`, `status`, `notes`, `created_at` | The incoming work queue. Each ticket points agents to the inventory, lease, or invoice rows they need. |
| `approvals` *(added by the MCP server in Problem 7)* | `id`, `kind` (invoice/rent/purchase), `ref_id`, `ticket_id`, `vendor_id`, `sku`, `size`, `qty`, `amount`, `account`, `reason`, `requested_by`, `resolves_ticket`, `status` (pending/approved/rejected), `created_at`, `decided_by`, `decided_at`, `result` | The checks waiting for a human. Agents can only add `pending` rows; only a human decision turns one into a payment. Created on first use, so a reset database simply gets it again. |

## MCP server

`mcp_server/server.py` is a FastMCP server named `campus-customs`. It is the only way agents touch the shop's data, and it reads `data/campus_customs_new.db` directly, so every answer comes from the database. Installed by the root `requirements.txt` (FastMCP 4.1); run with `python mcp_server/server.py` (stdio).

### Tools

#### `list_open_tickets()`
- **Reads:** `tickets` (rows where `status = 'open'`, oldest first).
- **Unlocks:** 101, 102, and 103. It's the first call for every ticket.
- **Why it's the right tool:** Each ticket's link fields (101 → `sku` CC-TEE-WHITE / `size` S / `invoice_id` 501, 102 → `lease_id` 1, 103 → `sku` CC-HOOD-NAVY / `size` M / `qty` 20) tell the agent exactly which inventory, invoice, or lease row to look up next, so it never has to guess what a ticket is about.

#### `check_stock_and_price(sku, size?)`
- **Reads:** `inventory` (qty and location per `sku` + `size`) joined with `pricing` (`list_price`, `unit_cost`).
- **Unlocks:** 101 and 103.
- **Why it's the right tool:**
  - **101:** Calling it with CC-TEE-WHITE / S returns `qty_on_hand = 0`, which proves Tauhid's tee can't ship from the shelf and that the order is waiting on the rush reprint (invoice 501).
  - **103:** Calling it with CC-HOOD-NAVY / M returns 8 on hand against the 20 the AI Club wants, plus a $58 list price over a $22 unit cost. That's the real shortfall and the real margin the agent needs before offering any bulk discount.

#### `get_cash_and_bills()`
- **Reads:** `desk` (today's date), `cash_accounts`, `invoices` joined with `vendors` (name, `lead_days`), and `leases`.
- **Unlocks:** 102, plus the payment side of 101.
- **Why it's the right tool:**
  - **102:** It shows lease 1's $2,400 rent due 2026-09-02 next to the $3,400 checking balance, so the agent can tell whether rent is covered and how much is left for other bills.
  - **101:** It flags invoice 501 ($840 to Bulldog Print Co, due 08-28) as overdue with a 5-day lead time. Paying rent and the invoice together leaves just $160, which is the tradeoff a human has to approve.

### Connecting to the vibe coder

`.mcp.json` at the HW 5 root registers the server with Claude Code as `campus-customs` (stdio). It launches `.venv/bin/python mcp_server/server.py` with paths relative to the project root, so it works on any machine after `python3 -m venv .venv`. Claude Code picks it up when a session is opened in the project folder and asks once to approve the project server. The backend and agents read the same file through `load_mcp_config()` in `backend/agents.py`, which resolves those paths against the project root (and falls back to the running Python if `.venv` is named differently), so `uvicorn` can start from `backend/`.

**Tested through Claude Code (2026-10-14):** in a session opened in `HW 5/`, every call went through `mcp__campus-customs__*` and matched the database:
- `list_open_tickets` returned 101, 102, 103 with their links.
- `check_stock_and_price` returned tee S = 0 ($28/$8), hoodie M = 8 ($58/$22), and `found: false` for a fake SKU.
- `get_cash_and_bills` returned $3,400 checking, invoice 501 $840 overdue, rent $2,400 due 09-02, $3,240 owed, and $160 left.

All three tools only read for now. Tools that write to the database will come in later problems.

### Tools added in Problem 5

| Tool | Reads / writes | Ticket it unlocks | Why |
|---|---|---|---|
| `get_ticket(ticket_id)` | reads `tickets`, `inventory` + `pricing`, `invoices` + `vendors`, `leases`, `desk` | 101, 102, 103 | One call gives an agent the ticket and every row it links to, e.g. 101 → tee S stock + invoice 501 + Bulldog Print Co, so delegated agents don't need to rebuild the links. |
| `list_vendors()` | reads `vendors` | 101, 103 | Inventory needs `lead_days` from the apparel reprint vendor to give a real restock date for the tee S (101) and the 12 missing hoodies M (103). |
| `quote_bulk_price(sku, qty, discount_pct, size?)` | reads `pricing`, `inventory` | 103 | Turns the AI Club's discount request into real numbers (order total, margin, below-cost check, shortfall) before anyone agrees to a price. Calculates only. |
| `update_ticket(ticket_id, status, note)` | writes `tickets.status`, appends to `tickets.notes` | 101, 102, 103 | Moves a ticket to `in_progress`, `waiting_on_approval`, or `resolved` with a dated note, so the queue shows where each one stands. |
| `adjust_inventory(sku, size, change, reason)` | writes `inventory.qty` | 101, 103 | Stock only changes when units actually leave or arrive. It refuses to go below zero, so the tee S at 0 can't be "sold". |
| ~~`record_payment`~~ | (removed in Problem 7) | | Replaced by `prepare_payment` + `decide_approval` (see Backend API below). Agents should never be able to move money, even with a typed approver name. |

`CAMPUS_CUSTOMS_DB` can point the server at another copy of the database. Test runs use a scratch copy so the working copy only changes when we mean it to.

### All MCP tools (final: 13)

| # | Tool | Tables read | Tables written | Agents that can call it | Ticket(s) it unlocks |
|---|---|---|---|---|---|
| 1 | `list_open_tickets()` | `tickets` | none | boss, customer_service | 101, 102, 103 (the queue) |
| 2 | `get_ticket(ticket_id)` | `tickets`, `inventory`, `pricing`, `invoices`, `vendors`, `leases`, `desk` | none | all five | 101, 102, 103 (one call gives every linked row) |
| 3 | `check_stock_and_price(sku, size?)` | `inventory`, `pricing` | none | inventory, customer_service | 101 (tee S = 0), 103 (hoodie M = 8) |
| 4 | `get_cash_and_bills()` | `desk`, `cash_accounts`, `invoices`, `vendors`, `leases` | none | boss, accounting, facilities | 102 (rent), 101 (invoice 501), the whole-shop cash check |
| 5 | `list_vendors()` | `vendors` | none | inventory, accounting, facilities | 101, 103 (5-day lead times) |
| 6 | `quote_bulk_price(sku, qty, discount_pct, size?)` | `pricing`, `inventory` | none | accounting, customer_service | 103 (10% → $52.20; 20% → $46.40) |
| 7 | `update_ticket(ticket_id, status, note)` | `tickets`, `desk` | `tickets` | boss, customer_service | 101, 102, 103 |
| 8 | `adjust_inventory(sku, size, change, reason)` | `inventory` | `inventory` | inventory | 101/103 when units actually move (never needed in the final run) |
| 9 | `prepare_payment(kind, ref_id, reason, requested_by, …)` | `invoices`/`leases`, `cash_accounts`, `approvals` | `approvals` (pending) | accounting | 101 (invoice 501 → #2), 102 (rent → #1) |
| 10 | `prepare_purchase(sku, size, qty, vendor_id, reason, requested_by, …)` | `pricing`, `inventory`, `vendors`, `cash_accounts`, `approvals` | `approvals` (pending) | inventory | 103 (12 hoodies → #3, $264) |
| 11 | `list_approvals(status?)` | `approvals` | none | boss, accounting; backend | stops duplicate requests (102 reused #1) |
| 12 | `decide_approval(approval_id, decision, decided_by, note?)` | `approvals`, `cash_accounts`, `invoices`, `leases`, `vendors`, `tickets` | `approvals`, `payments`, `cash_accounts`, `invoices`/`leases`, `tickets` | **no agent**: only `POST /api/approvals/{id}/approve|reject` | 101 (paid 501), 102 (paid rent → resolved) |
| 13 | `list_tickets()` | `tickets` | none | **no agent**: backend `/api/tickets` | the board |

(`record_payment` existed in Problem 5 and was removed in Problem 7, so no agent can move money.)

## Agent team (PydanticAI)

Code: `backend/agents.py` (team + delegation), `backend/models.py` (types), `backend/prompts/<role>.md` (one prompt per agent), `backend/run_team.py` (CLI). Every agent uses **gpt-6-luna** through Portkey (`PORTKEY_API_KEY`) via the OpenAI **Responses** API; chat completions rejects function tools for this model.

| Agent | Output type | MCP tools | Owns |
|---|---|---|---|
| `boss` | `BossBrief` | `list_open_tickets`, `get_ticket`, `get_cash_and_bills`, `update_ticket`, `list_approvals` | Triage, assigning owners, the whole-shop cash check, the brief to the owner |
| `inventory` | `AgentReport` | `get_ticket`, `check_stock_and_price`, `list_vendors`, `adjust_inventory`, `prepare_purchase` | Counts by size, shortfalls, restock dates (today + vendor lead days, only once the vendor is paid) |
| `accounting` | `AgentReport` | `get_ticket`, `get_cash_and_bills`, `quote_bulk_price`, `list_vendors`, `prepare_payment`, `list_approvals` | Cash, bills, preparing payments for the owner, discount rules |
| `facilities` | `AgentReport` | `get_ticket`, `get_cash_and_bills`, `list_vendors` | Lease, landlord, rent due dates; hands the payment itself to Accounting |
| `customer_service` | `AgentReport` | `list_open_tickets`, `get_ticket`, `check_stock_and_price`, `quote_bulk_price`, `update_ticket` | Customer orders and price requests; drafts replies that never reveal costs or bills |

### Delegation loop (full connectivity)
- Every agent has `ask_teammate(teammate, request)` and can reach **any** of the other four. The call runs that teammate as a nested agent run and returns its report as JSON.
- All nested runs share one usage budget (`UsageLimits(request_limit=80, tool_calls_limit=120)`) and one MCP server process.
- `TeamDeps.chain` tracks who is waiting on whom. A hand-off is refused, with a message back to the model, if it targets the agent itself, an agent already in the chain (a loop), or goes deeper than 3 levels.
- Every hand-off is logged as a `DelegationEvent` (from, to, request, result summary, or why it was refused). `run_team` returns these in `TeamResult.delegations`.
- Any agent can be the entry point (`run_team(..., entry="customer_service")`). The Boss is the default.

### Shop rules written into the prompts
- Only database numbers, using the shop's date (`desk.date_today`), never the real calendar.
- Agents only prepare payments and purchases; a named human approves them on the dashboard (`decide_approval`, which no agent can call).
- Cash cushion: flag anything that leaves checking under $500. Rent comes first among competing bills, but the owner decides.
- Discounts: list price by default. Bulk means 10+ units of one sku. Accounting can approve up to 10%; 10–20% needs the owner; never over 20% or below cost.
- Restock date = today + vendor `lead_days`, and only after any blocking vendor invoice is paid.
- Customer Service never shares costs, margins, cash, unpaid bills, or vendor names with customers.

### Audit trail (`output/audit_trail.json`)
`backend/audit.py` appends to one JSON array and never clears it. Each write goes through a temp file and an atomic replace. If the file is unreadable, it's renamed aside instead of overwritten. `run_agent_loop` drives each agent with `agent.iter`, so every loop step gets its own entry. Every entry has `ts`, `run_id`, `agent`, `chain`, `depth`, `step`, `kind`, and `usage_so_far` (requests, tool calls, input/output tokens).

| `kind` | Extra fields | What it lets you audit |
|---|---|---|
| `team_run_start` | `entry_agent`, `message`, `model`, `database`, `limits` | Who asked what, against which DB copy, under which budget |
| `agent_start` | `prompt` | The exact request an agent received, including delegated ones |
| `model_request` | `parts`: prompt / `tool_result` (tool, call id, content) / `retry` | What the model saw, including every MCP result it based its answer on |
| `model_response` | `model`, `finish_reason`, `parts`: `text` / `tool_call` (tool, call id, args) | What the model decided, including every MCP call and every `ask_teammate` hand-off with its arguments |
| `delegation_refused` | `to_agent`, `request`, `reason` (`self`, `loop`, `too_deep`) | Blocked hand-offs |
| `final` | `output` (the typed `AgentReport` / `BossBrief`) | Each agent's final answer |
| `error` | `error` | Where and why a loop failed |
| `team_run_end` | `status`, `delegations`, `usage` (or `error`) | The whole delegation tree and total spend |

## Safety

### Guardrails for real customers and real money
- **Agents can't move money at all.** They only queue requests (`prepare_payment`, `prepare_purchase`). `decide_approval` is the only money-moving tool, and it's in no agent's tool list. Only the backend's approve route calls it, after a human clicks Approve, and it rejects agent names as the decider.
- **Approvals find their ticket from the database.** `decide_approval` links a payment to every ticket whose `lease_id` / `invoice_id` matches what's being paid, not just the `ticket_id` the agent typed. In the final run, rent request #1 was drafted during ticket 101 without a ticket link, and signing it still resolved ticket 102.
- **Amounts come from the database, not the model.** `prepare_payment` and `prepare_purchase` compute the amount themselves (bill amount, or qty × unit cost). `decide_approval` re-checks the balance and the bill's status, so nothing can be paid twice or overdrawn.
- **No overdrafts.** Payments are refused if the account balance is too low, and the prompts require flagging anything that leaves checking under a $500 cushion.
- **Least privilege per role.** Each agent only sees its slice of MCP tools (`ROLE_TOOLS`). Only Accounting can prepare bill payments, only Inventory can prepare restocks or change stock, and Facilities can't write anything.
- **Writes validate their inputs.** Stock never goes below zero, ticket statuses come from a fixed list, and every write needs a reason or note that ends up in the database.
- **Single source of truth.** All shop facts go through the MCP server; agents have no other data path. Prompts forbid invented numbers and require each fact to cite the tool it came from (`Fact.source_tool`).
- **Customer privacy and discretion.** Customer Service never reveals costs, margins, cash, unpaid bills, or vendor names, never shares one customer's info with another, and never takes payment details in chat.
- **Discount ceiling.** Up to 10% with Accounting's OK, 10–20% needs the owner, never over 20% or below cost. `quote_bulk_price` flags `sells_below_cost`.
- **Safe testing.** `CAMPUS_CUSTOMS_DB` / `--db` runs the team on a scratch copy, so experiments don't touch the working DB.
- **Full audit trail.** Every prompt, tool call, tool result, hand-off, and final answer is appended to `output/audit_trail.json`.
- **Known agent weaknesses seen in the final run** (to tighten in prompts):
  - The Boss fans out to every relevant specialist at once, so Inventory got the same question up to 3 times.
  - Accounting drafted a bill for another ticket.
  - Customer Service and Accounting ran in parallel, so the approved 10% discount never reached the customer reply.

  None of these caused a wrong number or an unapproved payment.
- **Still needed before real use:** login and roles on the approve route (right now anyone who can reach the API can type a name), a dollar cap per approval, and alerts on refused or failed writes.

### Limits that keep token use in check
- **One shared budget per team run.** Nested delegated runs pass `usage=ctx.usage`, so all five agents draw from the same `UsageLimits(request_limit=40, tool_calls_limit=60, total_tokens_limit=400_000)`. Hitting it stops the run with `UsageLimitExceeded`, which is logged as an `error` step.
- **Per call:** `ModelSettings(timeout=90, max_tokens=4000)`, so one slow or rambling model call can't run forever.
- **Whole run:** `asyncio.timeout(600)` around the team run. (An earlier run with no audit trail or timeout hung for over 7 minutes with no visibility, which is why both were added.)
- **No delegation loops:** an agent can't ask itself or anyone already waiting in the chain, and chains stop at depth 3.
- **Small tool results:** tools return only the rows a ticket needs (e.g. `get_ticket` filters stock to the ticket's size), and the audit clips any field over 6,000 characters.
- **Prompts ask for one well-scoped request per teammate per ticket**, with no repeat questions.

## Backend API (`backend/main.py`, FastAPI)

Start it from `HW 5/backend` with `uvicorn main:app --reload --port 8000`, using the HW 5 venv (`source ../.venv/bin/activate` first, or run `../.venv/bin/python -m uvicorn main:app --reload --port 8000`, which is what the `hw5-backend` launch config does). The dashboard calls it at `http://localhost:8000`. Every route reads and writes shop data through the same campus-customs MCP server (`.mcp.json`), with no SQL in the backend. The only exception is `/api/reset`, which is a file copy. CORS allows any `localhost` / `127.0.0.1` port for the React dashboard.

### Routes (one line each)
- `GET  /api/health`: is the server up, and is an agent run going right now
- `GET  /api/tickets`: all tickets with their database `status`, the board `state` (`open` / `working` / `resolved`, where resolved means the team finished a run on it since the last reset or the DB says resolved), and how many requests are waiting for a signature (via `list_tickets`, `list_approvals`)
- `POST /api/tickets/{id}/run`: start the agent team on that ticket in the background; returns a `run_id` (404 unknown ticket, 409 if busy)
- `GET  /api/runs`: every run since the server started, newest first
- `GET  /api/runs/{run_id}`: one run's status (`running` / `done` / `failed`) and the Boss's final brief
- `GET  /api/events?after=&limit=&run_id=&ticket_id=`: recent agent events from the audit trail: who spoke, what they said, which tools they called, and whom they delegated to
- `GET  /api/approvals?status=pending|approved|rejected|all`: payment and purchase requests the agents prepared, each with its payee name (via `list_approvals`, `list_vendors`, `get_cash_and_bills`)
- `POST /api/approvals/{id}/approve` `{"decided_by": "<name>"}`: a human approves, and this is **the only route that changes cash** (via `decide_approval`)
- `POST /api/approvals/{id}/reject` `{"decided_by": "<name>", "note": ""}`: a human rejects; no money moves
- `GET  /api/cash`: current checking balance from `cash_accounts` (via `get_cash_and_bills`)
- `POST /api/reset`: copy `data/campus_customs.db` over `data/campus_customs_new.db` for a fresh run (audit trail kept)

### Route details

| Route | What it does | MCP tool / source |
|---|---|---|
| `GET /api/tickets` | All tickets with `status`, a simple `state` (`open` / `resolved`), and the ticket's latest run | `list_tickets` |
| `POST /api/tickets/{id}/run` | Starts the agent team on one ticket in the background and returns `202` with a `run_id` right away. `404` for an unknown ticket, `409` if a run is already going (one at a time). | `get_ticket`, then `run_team` |
| `GET /api/runs`, `GET /api/runs/{run_id}` | Run status (`running` / `done` / `failed`) and the Boss's final brief | in memory |
| `GET /api/events?after=&limit=&run_id=&ticket_id=` | Recent agent events, oldest first, each with `seq`, `agent`, `depth`, `kind`, `said` (what the agent said), `tools` (calls with args, or results), and `delegated_to`. Poll with `after=<last seq>` to get only new events. | `output/audit_trail.json` |
| `GET /api/approvals?status=pending\|approved\|rejected\|all` | Requests the agents prepared | `list_approvals` |
| `POST /api/approvals/{id}/approve` body `{"decided_by": "Lucy Guo"}` | **The only route that changes cash.** Pays the bill or places the restock, writes `payments`, and updates the ticket. Logged as a `human_decision` in the audit trail. | `decide_approval` |
| `POST /api/approvals/{id}/reject` | Closes the request without paying, with a note on the ticket | `decide_approval` |
| `GET /api/cash` | Current checking balance and as-of date | `get_cash_and_bills` |
| `POST /api/reset` | Copies `data/campus_customs.db` over `data/campus_customs_new.db` (`409` while a run is going). The audit trail is kept, with a `database_reset` entry marking the boundary. | file copy |

### Money flow
1. During a run, Accounting calls `prepare_payment` (invoice 501, rent) and Inventory calls `prepare_purchase` (restocks). Each adds a `pending` row to `approvals`, and **cash doesn't change**.
2. The dashboard lists them from `GET /api/approvals`.
3. A human clicks Approve, and `POST /api/approvals/{id}/approve` → `decide_approval`:
   - writes `payments` with `approved_by` = the human
   - lowers `cash_accounts.balance`
   - marks the invoice `paid`, moves rent to next month, or records the order and its arrival date
   - updates the linked ticket (rent → `resolved`; others → `in_progress`)

## Dashboard (`frontend/`, React + Vite + TypeScript)

Start the backend first (`uvicorn main:app --reload --port 8000` in `backend/`), then run `npm install` and `npm run dev` in `frontend/`. That opens the desk at `http://localhost:5173` (the `hw5-frontend` launch config runs the same command).

- **Frontend → backend:** the page calls the API directly at `http://localhost:8000`, set in `frontend/.env` as `VITE_API_BASE` (also the default in `src/api.ts`).
- **CORS:** `backend/main.py` allows the Vite origin (`http://localhost:5173` and `http://127.0.0.1:5173`, plus any other localhost port in case Vite picks the next free one) for `GET`/`POST` with a `content-type` header. Other origins get no CORS header, so a random website can't call the approve route from your browser.
- **Design notes:** see `output/design.md` for the look and the reasons behind it.

**Theme: shop front desk.** Wood-grain desk, a cork board with paper tickets pinned at slight angles, rubber stamps (OPEN / TEAM ON IT / RESOLVED), brass nameplates, handwritten notes (Caveat), typewriter ticket text (Special Elite), a green cash register, and checks waiting for a signature.

| Area | What it shows | Routes |
|---|---|---|
| Ticket board (`Corkboard.tsx`) | All three tickets as pinned paper tickets with a status stamp, the latest note, the DB status, and "N awaiting your signature". Click a ticket to select it; "Send to the team →" starts a run (disabled while another run is going). | `GET /api/tickets`, `POST /api/tickets/{id}/run` |
| The desks (`DeskFloor.tsx`) | One desk per agent with its own color, icon, name, and personality. A status lamp shows at desk / thinking / working / waiting on a teammate / done, and a speech bubble shows what it's doing right now ("Counting CC-HOOD-NAVY · size M", "Asking Accounting…"), plus hand-off chips and the tools it used. Agents not called show "Standing by" during a run and "Not needed on this ticket" afterward. | `GET /api/events?run_id=&after=` every 1.2 s while live |
| Who did what (`RunReport.tsx`) | The Boss's memo (summary, cash position, decisions needed), then an index card per agent: its final summary, who asked it, who it asked, tools used with counts, any payment/restock it drafted, and Customer Service's draft reply. Footer shows duration, model calls, tool calls, and tokens. | events (`final`, `team_run_end`) |
| Desk log (`DeskLog.tsx`) | Lined notebook of every step: hand-offs ("Boss → Accounting: …"), tool calls in plain words, final answers, refusals, errors. Indented by delegation depth, auto-scrolls while live. | events |
| Cash drawer (`CashDrawer.tsx`) | Checking balance in a register display that counts down and flashes a red "−$2,400" when a signed payment lands, plus a bar with the $500 cushion marker, total waiting for signature, and "if you sign everything". | `GET /api/cash` |
| Needs your signature (`SignatureTray.tsx`) | Each prepared payment or restock as a check (payee, amount, memo, reason, drafting agent). Type your name once ("Signing as"), then **Sign & pay** / **Sign & order** or **Void**. History of signed and voided checks. | `GET /api/approvals`, `POST /api/approvals/{id}/approve`, `/reject` |
| Top bar | Shop date from the database, backend connection lamp, and **↺ Fresh day** (reset, with confirm). | `POST /api/reset` |

**Agent personas** (`src/agents.ts`):
- **Boss**: Margaret Hale 🧭, navy. "Calm, decisive. Sees the whole shop."
- **Inventory**: Theo Park 📦, olive. "Counts twice. Knows every aisle."
- **Accounting**: Priya Desai 🧮, teal. "Precise to the cent. Nothing leaves without a signature."
- **Facilities**: Gus Moreno 🔑, rust. "Keeps the lights on and the landlord happy."
- **Customer Service**: Bea Lindqvist 💬, rose. "Warm, upbeat, a little Bulldog spirit."

**"Resolved" on the board** means the team finished its run on the ticket. The ticket can still have a check waiting for a signature (shown on the card), and the DB status underneath stays honest (e.g. `waiting_on_approval`). Signing a rent payment also sets the DB status to `resolved`.

**Note on Portkey caching:** re-running a ticket on an identical database state can return cached model responses (a 21-call run finished in 7 s with the same wording as before). The tool calls still hit the real database. If the data has changed, the prompts differ and the run is fresh.

## Final run results (Problem 9)

Fresh database (reset 2026-10-14 20:30 UTC) → tickets 101, 102, 103 run from the board one at a time → two checks signed by Lucy Guo on the board.

| Ticket | Run | Agents involved | Board | DB status | Human approvals | Cash |
|---|---|---|---|---|---|---|
| 101 tee S | `d6b9f190ff74`, 1m59s, 19 model / 21 tool calls | Boss, Customer Service, Inventory ×2, Accounting ×2 | resolved | `in_progress` (reprint coming) | #2 invoice 501 $840, **approved** | −$840.00 |
| 102 rent | `c3de9b35ad94`, 35s, 13 / 15 | Boss, Facilities, Accounting ×2 | resolved | `resolved` | #1 rent $2,400, **approved** | −$2,400.00 |
| 103 hoodies | `25fe6c9267f0`, 49s, 23 / 24 | Boss, Customer Service, Accounting, Inventory ×3 | resolved | `waiting_on_approval` | #3 restock $264, **held** (not enough cash) | $0.00 |

**Checking: $3,400.00 → $160.00** (−$3,240.00). This matches `cash_accounts.checking = 160.0` and `SUM(payments.amount) = 3240.0` in `data/campus_customs_new.db`.

| Deliverable | What it shows |
|---|---|
| `output/desk_tickets.html` | Expected vs. Actual per ticket, plus the Cash ledger |
| `output/resolved_tickets.json` | Per ticket: status, outcome, each agent's contribution, human approvals, and run stats |
| `output/resolved_board.html` | Board screenshots per resolved ticket, with images embedded so it opens with a double-click |
| `output/audit_trail.json` | All of it, append-only: 441 entries over 9 team runs, plus 8 human decisions and 3 resets at the time of writing |
