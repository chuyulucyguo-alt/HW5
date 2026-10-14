"""Campus Customs MCP server.

Every agent in this homework reaches the shop's data through these tools.
All answers come straight from data/campus_customs_new.db; nothing is made up.
"""

import os
import sqlite3
from pathlib import Path

from fastmcp import FastMCP
from pydantic import BaseModel

DB_PATH = Path(
    os.getenv("CAMPUS_CUSTOMS_DB")
    or Path(__file__).resolve().parent.parent / "data" / "campus_customs_new.db"
)

mcp = FastMCP(
    "campus-customs",
    instructions=(
        "Tools for the Campus Customs shop database. Only report what the tools "
        "return; if a tool finds nothing, say so instead of guessing."
    ),
)


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------- Result types ----------


class Ticket(BaseModel):
    id: int
    type: str
    requester: str
    subject: str
    sku: str | None
    size: str | None
    qty: int | None
    lease_id: int | None
    invoice_id: int | None
    status: str
    notes: str | None
    created_at: str


class StockLine(BaseModel):
    sku: str
    name: str
    size: str
    qty_on_hand: int
    location: str
    list_price: float | None
    unit_cost: float | None


class StockAndPrice(BaseModel):
    sku: str
    found: bool
    lines: list[StockLine]
    message: str


class CashAccount(BaseModel):
    name: str
    balance: float
    as_of: str


class OpenInvoice(BaseModel):
    id: int
    vendor_id: int
    vendor_name: str
    vendor_lead_days: int
    amount: float
    due_date: str
    status: str
    description: str | None
    overdue: bool


class LeaseDue(BaseModel):
    id: int
    space_name: str
    landlord: str
    monthly_rent: float
    next_due: str
    notes: str | None


class CashAndBills(BaseModel):
    today: str
    cash_accounts: list[CashAccount]
    total_cash: float
    open_invoices: list[OpenInvoice]
    leases: list[LeaseDue]
    total_owed: float
    cash_after_all_bills: float


# ---------- Tools ----------


@mcp.tool
def list_open_tickets() -> list[Ticket]:
    """List every ticket whose status is 'open', oldest first, with its linked
    sku/size/qty, lease_id, and invoice_id so you know what to look up next."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM tickets WHERE status = 'open' ORDER BY created_at"
        ).fetchall()
    return [Ticket(**dict(r)) for r in rows]


@mcp.tool
def check_stock_and_price(sku: str, size: str | None = None) -> StockAndPrice:
    """Look up how many units of a product are on hand (per size) and its list
    price and unit cost. Pass a size like 'S', 'M', or 'OS' to narrow it down;
    leave it out to see every size."""
    sql = (
        "SELECT i.sku, i.name, i.size, i.qty AS qty_on_hand, i.location, "
        "p.list_price, p.unit_cost "
        "FROM inventory i LEFT JOIN pricing p ON p.sku = i.sku WHERE i.sku = ?"
    )
    params: list = [sku]
    if size:
        sql += " AND i.size = ?"
        params.append(size)
    with _connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    lines = [StockLine(**dict(r)) for r in rows]
    if not lines:
        where = f"{sku} size {size}" if size else sku
        return StockAndPrice(
            sku=sku, found=False, lines=[], message=f"No inventory record for {where}."
        )
    total = sum(line.qty_on_hand for line in lines)
    return StockAndPrice(
        sku=sku, found=True, lines=lines, message=f"{total} unit(s) on hand."
    )


@mcp.tool
def get_cash_and_bills() -> CashAndBills:
    """Show the shop's cash balance next to everything it owes: open vendor
    invoices (flagged if overdue) and upcoming rent. Use this before deciding
    whether any bill can be paid."""
    with _connect() as conn:
        today = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()[0]
        accounts = [
            CashAccount(name=r["name"], balance=r["balance"], as_of=r["date"])
            for r in conn.execute("SELECT * FROM cash_accounts ORDER BY name")
        ]
        invoices = [
            OpenInvoice(
                id=r["id"],
                vendor_id=r["vendor_id"],
                vendor_name=r["vendor_name"],
                vendor_lead_days=r["lead_days"],
                amount=r["amount"],
                due_date=r["due_date"],
                status=r["status"],
                description=r["description"],
                overdue=r["due_date"] < today,
            )
            for r in conn.execute(
                "SELECT inv.*, v.name AS vendor_name, v.lead_days "
                "FROM invoices inv JOIN vendors v ON v.id = inv.vendor_id "
                "WHERE inv.status = 'open' ORDER BY inv.due_date"
            )
        ]
        leases = [
            LeaseDue(**dict(r))
            for r in conn.execute("SELECT * FROM leases ORDER BY next_due")
        ]
    total_cash = sum(a.balance for a in accounts)
    total_owed = sum(i.amount for i in invoices) + sum(l.monthly_rent for l in leases)
    return CashAndBills(
        today=today,
        cash_accounts=accounts,
        total_cash=total_cash,
        open_invoices=invoices,
        leases=leases,
        total_owed=total_owed,
        cash_after_all_bills=total_cash - total_owed,
    )


# ---------- More result types ----------


class Vendor(BaseModel):
    id: int
    name: str
    specialty: str
    lead_days: int


class TicketDetail(BaseModel):
    ticket: Ticket | None
    found: bool
    stock: list[StockLine]
    invoice: OpenInvoice | None
    vendor: Vendor | None
    lease: LeaseDue | None
    today: str
    message: str


class BulkQuote(BaseModel):
    sku: str
    found: bool
    qty_requested: int
    qty_on_hand: int | None
    shortfall: int | None
    list_price: float | None
    unit_cost: float | None
    discount_pct: float
    unit_price_after_discount: float | None
    order_total: float | None
    margin_per_unit: float | None
    margin_pct: float | None
    sells_below_cost: bool | None
    message: str


class WriteResult(BaseModel):
    ok: bool
    message: str


TICKET_STATUSES = {"open", "in_progress", "waiting_on_approval", "resolved"}
AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer service", "customer_service", "agent"}


# ---------- More read tools ----------


@mcp.tool
def get_ticket(ticket_id: int) -> TicketDetail:
    """Open one ticket and everything it links to in a single call: the stock
    and price rows for its sku/size, its invoice and that invoice's vendor,
    and its lease. Use this before working on any ticket."""
    with _connect() as conn:
        today = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()[0]
        row = conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return TicketDetail(
                ticket=None, found=False, stock=[], invoice=None, vendor=None,
                lease=None, today=today, message=f"No ticket with id {ticket_id}.",
            )
        ticket = Ticket(**dict(row))
        stock: list[StockLine] = []
        if ticket.sku:
            sql = (
                "SELECT i.sku, i.name, i.size, i.qty AS qty_on_hand, i.location, "
                "p.list_price, p.unit_cost FROM inventory i "
                "LEFT JOIN pricing p ON p.sku = i.sku WHERE i.sku = ?"
            )
            params: list = [ticket.sku]
            if ticket.size:
                sql += " AND i.size = ?"
                params.append(ticket.size)
            stock = [StockLine(**dict(r)) for r in conn.execute(sql, params)]
        invoice = vendor = None
        if ticket.invoice_id is not None:
            r = conn.execute(
                "SELECT inv.*, v.name AS vendor_name, v.lead_days, v.specialty "
                "FROM invoices inv JOIN vendors v ON v.id = inv.vendor_id WHERE inv.id = ?",
                (ticket.invoice_id,),
            ).fetchone()
            if r:
                invoice = OpenInvoice(
                    id=r["id"], vendor_id=r["vendor_id"], vendor_name=r["vendor_name"],
                    vendor_lead_days=r["lead_days"], amount=r["amount"], due_date=r["due_date"],
                    status=r["status"], description=r["description"],
                    overdue=r["status"] == "open" and r["due_date"] < today,
                )
                vendor = Vendor(id=r["vendor_id"], name=r["vendor_name"],
                                specialty=r["specialty"], lead_days=r["lead_days"])
        lease = None
        if ticket.lease_id is not None:
            r = conn.execute("SELECT * FROM leases WHERE id = ?", (ticket.lease_id,)).fetchone()
            if r:
                lease = LeaseDue(**dict(r))
    return TicketDetail(
        ticket=ticket, found=True, stock=stock, invoice=invoice, vendor=vendor,
        lease=lease, today=today, message=f"Ticket {ticket_id} loaded.",
    )


@mcp.tool
def list_vendors() -> list[Vendor]:
    """List every vendor with what they supply and how many days they take
    (lead_days). Use this to say who can restock an item and by when."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM vendors ORDER BY id").fetchall()
    return [Vendor(**dict(r)) for r in rows]


@mcp.tool
def quote_bulk_price(sku: str, qty: int, discount_pct: float = 0, size: str | None = None) -> BulkQuote:
    """Work out what a bulk order would cost at a given discount, using the
    real list price and unit cost. Shows the order total, margin per unit,
    whether the discount would sell below cost, and how many units are short
    if size is given. This only calculates; it does not change any price."""
    with _connect() as conn:
        price = conn.execute("SELECT * FROM pricing WHERE sku = ?", (sku,)).fetchone()
        stock_sql = "SELECT SUM(qty) FROM inventory WHERE sku = ?"
        params: list = [sku]
        if size:
            stock_sql += " AND size = ?"
            params.append(size)
        on_hand = conn.execute(stock_sql, params).fetchone()[0]
    if price is None or qty <= 0 or not 0 <= discount_pct <= 100:
        reason = (f"No price on file for {sku}." if price is None
                  else "qty must be positive and discount_pct between 0 and 100.")
        return BulkQuote(
            sku=sku, found=price is not None, qty_requested=qty, qty_on_hand=on_hand,
            shortfall=None, list_price=None, unit_cost=None, discount_pct=discount_pct,
            unit_price_after_discount=None, order_total=None, margin_per_unit=None,
            margin_pct=None, sells_below_cost=None, message=reason,
        )
    unit = round(price["list_price"] * (1 - discount_pct / 100), 2)
    margin = round(unit - price["unit_cost"], 2)
    shortfall = max(qty - on_hand, 0) if on_hand is not None else None
    return BulkQuote(
        sku=sku, found=True, qty_requested=qty, qty_on_hand=on_hand, shortfall=shortfall,
        list_price=price["list_price"], unit_cost=price["unit_cost"], discount_pct=discount_pct,
        unit_price_after_discount=unit, order_total=round(unit * qty, 2),
        margin_per_unit=margin, margin_pct=round(100 * margin / unit, 1) if unit else None,
        sells_below_cost=margin < 0,
        message=f"{qty} x {sku} at {discount_pct:g}% off = ${unit * qty:,.2f}.",
    )


# ---------- Write tools (change campus_customs_new.db) ----------


@mcp.tool
def update_ticket(ticket_id: int, status: str, note: str) -> WriteResult:
    """Change a ticket's status and append a dated note explaining why.
    status must be one of: open, in_progress, waiting_on_approval, resolved."""
    if status not in TICKET_STATUSES:
        return WriteResult(ok=False, message=f"status must be one of {sorted(TICKET_STATUSES)}.")
    if not note.strip():
        return WriteResult(ok=False, message="A note explaining the change is required.")
    with _connect() as conn:
        today = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()[0]
        row = conn.execute("SELECT notes FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        if row is None:
            return WriteResult(ok=False, message=f"No ticket with id {ticket_id}.")
        notes = (row["notes"] or "").rstrip()
        notes = f"{notes}\n[{today}] {status}: {note.strip()}".strip()
        conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, ticket_id))
    return WriteResult(ok=True, message=f"Ticket {ticket_id} set to {status}.")


@mcp.tool
def adjust_inventory(sku: str, size: str, change: int, reason: str) -> WriteResult:
    """Add (positive change) or remove (negative change) units for one sku and
    size, e.g. -1 when an order ships or +N when a restock arrives. Refuses to
    take stock below zero."""
    if change == 0 or not reason.strip():
        return WriteResult(ok=False, message="change must be non-zero and a reason is required.")
    with _connect() as conn:
        row = conn.execute(
            "SELECT qty FROM inventory WHERE sku = ? AND size = ?", (sku, size)
        ).fetchone()
        if row is None:
            return WriteResult(ok=False, message=f"No inventory record for {sku} size {size}.")
        new_qty = row["qty"] + change
        if new_qty < 0:
            return WriteResult(
                ok=False, message=f"Only {row['qty']} of {sku} size {size} on hand; cannot remove {-change}."
            )
        conn.execute(
            "UPDATE inventory SET qty = ? WHERE sku = ? AND size = ?", (new_qty, sku, size)
        )
    return WriteResult(ok=True, message=f"{sku} size {size}: {row['qty']} -> {new_qty} ({reason.strip()}).")


# ---------- Approval queue: agents prepare, a human decides ----------
#
# Agents can only *prepare* money going out (prepare_payment / prepare_purchase), which adds a
# pending row to `approvals`. Cash changes only in decide_approval, which no agent is given; the
# FastAPI backend calls it when a human clicks Approve on the dashboard.

APPROVALS_SCHEMA = """
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,              -- invoice | rent | purchase
    ref_id INTEGER,                  -- invoices.id or leases.id (NULL for purchases)
    ticket_id INTEGER,
    vendor_id INTEGER,
    sku TEXT, size TEXT, qty INTEGER,
    amount REAL NOT NULL,            -- always computed from the database, never from the agent
    account TEXT NOT NULL,
    reason TEXT NOT NULL,
    requested_by TEXT NOT NULL,      -- the agent that prepared it
    resolves_ticket INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,            -- pending | approved | rejected
    created_at TEXT NOT NULL,
    decided_by TEXT, decided_at TEXT, result TEXT
)
"""
CASH_CUSHION = 500.0


class Approval(BaseModel):
    id: int
    kind: str
    ref_id: int | None
    ticket_id: int | None
    vendor_id: int | None
    sku: str | None
    size: str | None
    qty: int | None
    amount: float
    account: str
    reason: str
    requested_by: str
    resolves_ticket: bool
    status: str
    created_at: str
    decided_by: str | None
    decided_at: str | None
    result: str | None


class PrepareResult(BaseModel):
    ok: bool
    approval_id: int | None
    amount: float | None
    balance_now: float | None
    balance_after: float | None
    below_cushion: bool | None
    message: str


def _db() -> sqlite3.Connection:
    conn = _connect()
    conn.execute(APPROVALS_SCHEMA)
    return conn


def _today(conn) -> str:
    return conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()[0]


def _queue(conn, *, kind, ref_id, ticket_id, vendor_id, sku, size, qty, amount, account,
           reason, requested_by, resolves_ticket) -> PrepareResult:
    acct = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (account,)).fetchone()
    if acct is None:
        return PrepareResult(ok=False, approval_id=None, amount=amount, balance_now=None,
                             balance_after=None, below_cushion=None, message=f"No cash account named {account}.")
    dup = conn.execute(
        "SELECT id FROM approvals WHERE status = 'pending' AND kind = ? AND "
        "IFNULL(ref_id, -1) = IFNULL(?, -1) AND IFNULL(sku, '') = IFNULL(?, '') AND IFNULL(size, '') = IFNULL(?, '')",
        (kind, ref_id, sku, size),
    ).fetchone()
    balance = acct["balance"]
    after = balance - amount
    if dup:
        return PrepareResult(ok=True, approval_id=dup["id"], amount=amount, balance_now=balance,
                             balance_after=after, below_cushion=after < CASH_CUSHION,
                             message=f"Already waiting for approval as request #{dup['id']}; not added twice.")
    cur = conn.execute(
        "INSERT INTO approvals (kind, ref_id, ticket_id, vendor_id, sku, size, qty, amount, account, reason, "
        "requested_by, resolves_ticket, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'pending', ?)",
        (kind, ref_id, ticket_id, vendor_id, sku, size, qty, amount, account, reason.strip(),
         requested_by.strip(), int(resolves_ticket), _today(conn)),
    )
    note = " This would leave checking under the $500 cushion." if after < CASH_CUSHION else ""
    return PrepareResult(
        ok=True, approval_id=cur.lastrowid, amount=amount, balance_now=balance, balance_after=after,
        below_cushion=after < CASH_CUSHION,
        message=f"Request #{cur.lastrowid} for ${amount:,.2f} is waiting for a human to approve. "
                f"No money has moved. Balance now ${balance:,.2f}, ${after:,.2f} if approved.{note}",
    )


@mcp.tool
def prepare_payment(kind: str, ref_id: int, reason: str, requested_by: str,
                    ticket_id: int | None = None, account: str = "checking",
                    resolves_ticket: bool = False) -> PrepareResult:
    """Prepare (do NOT make) a payment of a bill for a human to approve.
    kind is 'invoice' (ref_id = invoices.id) or 'rent' (ref_id = leases.id). The
    amount is taken from the database. requested_by is your agent name. Set
    resolves_ticket=true only if paying fully finishes the ticket (e.g. rent).
    No cash moves until a human approves it on the dashboard."""
    if kind not in {"invoice", "rent"}:
        return PrepareResult(ok=False, approval_id=None, amount=None, balance_now=None, balance_after=None,
                             below_cushion=None, message="kind must be 'invoice' or 'rent'.")
    if not reason.strip():
        return PrepareResult(ok=False, approval_id=None, amount=None, balance_now=None, balance_after=None,
                             below_cushion=None, message="A reason is required.")
    with _db() as conn:
        if kind == "invoice":
            bill = conn.execute("SELECT amount, status, vendor_id FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if bill is None or bill["status"] != "open":
                msg = f"No invoice {ref_id}." if bill is None else f"Invoice {ref_id} is already {bill['status']}."
                return PrepareResult(ok=False, approval_id=None, amount=None, balance_now=None,
                                     balance_after=None, below_cushion=None, message=msg)
            amount, vendor_id = bill["amount"], bill["vendor_id"]
        else:
            lease = conn.execute("SELECT monthly_rent FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if lease is None:
                return PrepareResult(ok=False, approval_id=None, amount=None, balance_now=None,
                                     balance_after=None, below_cushion=None, message=f"No lease {ref_id}.")
            amount, vendor_id = lease["monthly_rent"], None
        return _queue(conn, kind=kind, ref_id=ref_id, ticket_id=ticket_id, vendor_id=vendor_id, sku=None,
                      size=None, qty=None, amount=amount, account=account, reason=reason,
                      requested_by=requested_by, resolves_ticket=resolves_ticket)


@mcp.tool
def prepare_purchase(sku: str, size: str, qty: int, vendor_id: int, reason: str, requested_by: str,
                     ticket_id: int | None = None, account: str = "checking") -> PrepareResult:
    """Prepare (do NOT place) a restock purchase for a human to approve. The
    cost is qty x the sku's unit_cost from pricing. requested_by is your agent
    name. Nothing is ordered and no cash moves until a human approves it."""
    if qty <= 0 or not reason.strip():
        return PrepareResult(ok=False, approval_id=None, amount=None, balance_now=None, balance_after=None,
                             below_cushion=None, message="qty must be positive and a reason is required.")
    with _db() as conn:
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        row = conn.execute("SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)).fetchone()
        vendor = conn.execute("SELECT id FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if price is None or row is None or vendor is None:
            return PrepareResult(ok=False, approval_id=None, amount=None, balance_now=None, balance_after=None,
                                 below_cushion=None, message=f"Unknown sku/size {sku} {size} or vendor {vendor_id}.")
        amount = round(qty * price["unit_cost"], 2)
        return _queue(conn, kind="purchase", ref_id=None, ticket_id=ticket_id, vendor_id=vendor_id, sku=sku,
                      size=size, qty=qty, amount=amount, account=account, reason=reason,
                      requested_by=requested_by, resolves_ticket=False)


@mcp.tool
def list_approvals(status: str | None = "pending") -> list[Approval]:
    """List payment/purchase requests waiting for (or already given) a human
    decision. status: 'pending', 'approved', 'rejected', or None for all."""
    with _db() as conn:
        if status:
            rows = conn.execute("SELECT * FROM approvals WHERE status = ? ORDER BY id", (status,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM approvals ORDER BY id").fetchall()
    return [Approval(**{**dict(r), "resolves_ticket": bool(r["resolves_ticket"])}) for r in rows]


@mcp.tool
def decide_approval(approval_id: int, decision: str, decided_by: str, note: str = "") -> WriteResult:
    """HUMAN ONLY - called by the dashboard backend, never given to an agent.
    decision 'approve' moves the money: writes payments, lowers the cash
    balance, and marks the invoice paid / moves rent to next month. 'reject'
    just closes the request. Either way the linked ticket gets a note."""
    if decision not in {"approve", "reject"}:
        return WriteResult(ok=False, message="decision must be 'approve' or 'reject'.")
    who = decided_by.strip()
    if not who or who.lower() in AGENT_NAMES or "agent" in who.lower():
        return WriteResult(ok=False, message="A named human must make this decision; agents cannot.")
    with _db() as conn:
        today = _today(conn)
        req = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if req is None:
            return WriteResult(ok=False, message=f"No approval request #{approval_id}.")
        if req["status"] != "pending":
            return WriteResult(ok=False, message=f"Request #{approval_id} was already {req['status']}.")
        new_status = "in_progress"
        if decision == "reject":
            result = f"Rejected by {who}." + (f" {note.strip()}" if note.strip() else "")
            conn.execute("UPDATE approvals SET status='rejected', decided_by=?, decided_at=?, result=? WHERE id=?",
                         (who, today, result, approval_id))
        else:
            acct = conn.execute("SELECT balance FROM cash_accounts WHERE name = ?", (req["account"],)).fetchone()
            if acct is None or acct["balance"] < req["amount"]:
                have = acct["balance"] if acct else 0
                return WriteResult(ok=False, message=f"{req['account']} has ${have:,.2f}; "
                                                     f"${req['amount']:,.2f} is needed. Nothing was paid.")
            if req["kind"] == "invoice":
                inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (req["ref_id"],)).fetchone()
                if inv is None or inv["status"] != "open":
                    return WriteResult(ok=False, message=f"Invoice {req['ref_id']} is no longer open. Nothing was paid.")
                conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
                result = f"Paid invoice {req['ref_id']}."
            elif req["kind"] == "rent":
                conn.execute("UPDATE leases SET next_due = date(next_due, '+1 month') WHERE id = ?", (req["ref_id"],))
                result = f"Paid rent for lease {req['ref_id']}; next due moved one month."
            else:
                lead = conn.execute("SELECT name, lead_days FROM vendors WHERE id = ?", (req["vendor_id"],)).fetchone()
                eta = conn.execute("SELECT date(?, ?)", (today, f"+{lead['lead_days']} days")).fetchone()[0]
                result = (f"Ordered {req['qty']} x {req['sku']} {req['size']} from {lead['name']}; "
                          f"expected around {eta}. Stock updates when it arrives.")
            conn.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) VALUES (?,?,?,?,?,?)",
                (req["kind"], req["ref_id"] if req["ref_id"] is not None else approval_id,
                 req["amount"], req["account"], today, who),
            )
            conn.execute("UPDATE cash_accounts SET balance = balance - ?, date = ? WHERE name = ?",
                         (req["amount"], today, req["account"]))
            left = acct["balance"] - req["amount"]
            result += f" ${req['amount']:,.2f} from {req['account']}, approved by {who}; ${left:,.2f} left."
            conn.execute("UPDATE approvals SET status='approved', decided_by=?, decided_at=?, result=? WHERE id=?",
                         (who, today, result, approval_id))
        # Link the decision to its ticket(s) from the database itself (tickets.lease_id / invoice_id),
        # not only from the ticket_id the agent passed, so a payment prepared in another ticket's run
        # still lands on the right ticket.
        linked = {req["ticket_id"]} if req["ticket_id"] is not None else set()
        if req["kind"] in {"rent", "invoice"} and req["ref_id"] is not None:
            col = "lease_id" if req["kind"] == "rent" else "invoice_id"
            linked |= {r["id"] for r in conn.execute(f"SELECT id FROM tickets WHERE {col} = ?", (req["ref_id"],))}
        for tid in sorted(linked):
            t = conn.execute("SELECT type, notes FROM tickets WHERE id = ?", (tid,)).fetchone()
            if t is None:
                continue
            status = new_status
            if decision == "approve" and (req["resolves_ticket"] or (req["kind"] == "rent" and t["type"] == "rent_notice")):
                status = "resolved"
            notes = f"{(t['notes'] or '').rstrip()}\n[{today}] {status}: request #{approval_id}: {result}".strip()
            conn.execute("UPDATE tickets SET status = ?, notes = ? WHERE id = ?", (status, notes, tid))
    return WriteResult(ok=True, message=result)


@mcp.tool
def list_tickets() -> list[Ticket]:
    """List every ticket (open, in progress, waiting on approval, or resolved), by id."""
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM tickets ORDER BY id").fetchall()
    return [Ticket(**dict(r)) for r in rows]


if __name__ == "__main__":
    mcp.run(show_banner=False)
