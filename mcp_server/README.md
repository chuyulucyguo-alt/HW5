# Campus Customs MCP server

A FastMCP server that gives every agent in HW 5 one shared path to the shop's data. Agents call these tools instead of querying SQLite themselves. Every answer comes straight from the database, and when the tools find nothing they say so instead of filling in made-up values.

**Database:** `data/campus_customs_new.db`, the working copy. The original `data/campus_customs.db` is never touched.

## Tools

The first three tools came from Problem 3. Problem 5 added the ticket, vendor, quote, and write tools. Problem 7 replaced the old `record_payment` with an approval queue: agents only prepare payments and purchases, and a human decides through the backend. The `approvals` table is created in the working copy the first time it's needed.

| Tool | Tables | Used by | What it does |
|---|---|---|---|
| `list_open_tickets()` | `tickets` | boss, customer_service | Lists open tickets with the SKU, size, quantity, lease, and invoice each one links to. |
| `check_stock_and_price(sku, size?)` | `inventory`, `pricing` | inventory, customer_service | Stock on hand for each size and the list price and unit cost; returns `found: false` for an unknown SKU. |
| `get_cash_and_bills()` | `desk`, `cash_accounts`, `invoices`, `vendors`, `leases` | boss, accounting, facilities | Cash balance, open vendor invoices (flagged if overdue), rent due, and the cash left after all bills. |
| `get_ticket(ticket_id)` | `tickets`, `inventory`, `pricing`, `invoices`, `vendors`, `leases`, `desk` | all five | One ticket plus the stock, invoice, vendor, and lease rows it links to. |
| `list_vendors()` | `vendors` | inventory, accounting, facilities | Vendors, what they supply, and their lead days. |
| `quote_bulk_price(sku, qty, discount_pct, size?)` | `pricing`, `inventory` | accounting, customer_service | Calculates a bulk order total, margin, below-cost check, and stock shortfall. Changes nothing. |
| `update_ticket(ticket_id, status, note)` | `tickets` (**writes**) | boss, customer_service | Sets status (`open`, `in_progress`, `waiting_on_approval`, `resolved`) and appends a dated note. |
| `adjust_inventory(sku, size, change, reason)` | `inventory` (**writes**) | inventory | Adds or removes stock; never below zero. |
| `prepare_payment(kind, ref_id, reason, requested_by, ticket_id?, account?, resolves_ticket?)` | reads `invoices`/`leases`, `cash_accounts`; **writes** `approvals` | accounting | Queues an invoice or rent payment for a human to approve, at the database amount. Moves no money; won't queue the same bill twice. |
| `prepare_purchase(sku, size, qty, vendor_id, reason, requested_by, ticket_id?)` | reads `pricing`, `inventory`, `vendors`, `cash_accounts`; **writes** `approvals` | inventory | Queues a restock order (qty × unit cost) for a human to approve. Orders nothing. |
| `list_approvals(status?)` | `approvals` | boss, accounting | Lists pending / approved / rejected payment and purchase requests. |
| `decide_approval(approval_id, decision, decided_by, note?)` | **writes** `approvals`, `payments`, `cash_accounts`, `invoices`/`leases`, `tickets` | **no agent**: only the backend's approve/reject routes | The only tool that moves money. Needs a named human; refuses if cash is short, the bill is no longer open, or the request was already decided. Updates every ticket linked to the paid lease or invoice (rent on a rent notice → `resolved`). |
| `list_tickets()` | `tickets` | **no agent**: backend `/api/tickets` | Every ticket with its status, for the dashboard. |

The agent team (`backend/agents.py`) and the FastAPI backend (`backend/main.py`) both connect to this server through `.mcp.json`. Neither has another way to read or change shop data.

Set `CAMPUS_CUSTOMS_DB` to point the server at a different copy of the database, e.g. for test runs.

## Run

From the project root (with the venv active):

```bash
pip install -r requirements.txt
python mcp_server/server.py
```

The server runs over stdio.
