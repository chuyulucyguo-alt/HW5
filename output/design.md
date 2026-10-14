# Campus Customs Front Desk: design notes

The dashboard in `frontend/` is the desk where a shop owner sits while five AI agents work the tickets. I didn't want an admin panel full of gray tables. I wanted the screen to look like the back room of a small campus shop: a wooden desk, a cork board of paper tickets, coworkers at their desks, a cash register, and a stack of checks waiting for a signature. Everything below follows from that one idea, **the shop front desk**.

## Layout: three zones, read left to right like real work

| Left: *the work* | Middle: *the people* | Right: *the money* |
|---|---|---|
| **Ticket board**: a cork board with the three tickets pinned on it | **The desks**: the Boss's desk on top, four specialists below. Under them: **Who did what** (the Boss's memo plus one index card per agent) and the **Desk log** notebook | **Cash drawer** (checking balance) and **Needs your signature** (checks to approve) |

- **Why this order.** It follows how the owner thinks: *what needs doing → who is doing it → what will it cost me*. You pick a ticket on the left, watch it travel through the people in the middle, and anything that touches money lands on the right, where your hand (and signature) is.
- **The two side columns are sticky.** The tickets and the cash stay in view while you scroll through a long run log, because those are the two things you glance at most.
- **The Boss's desk is wider and on top.** Every ticket starts there, and the Boss writes the final memo, so the layout mirrors the reporting line.
- **It collapses gracefully.** Under 1280px the money column moves under the work (cash and checks side by side). Under 820px everything stacks into one column.

## Materials and type: why it feels like a place, not a page

- **Wood-grain background** built from layered CSS gradients, plus a faint **paper grain** (SVG fractal noise) on every paper surface. Nothing is a flat color, and nothing loads an image file.
- **Cork board** with speckles and a wooden frame. **Tickets are paper stubs** with notched sides, tilted a degree or two (−2.2°, +1.6°, −1.1°) and held by **colored push pins**. When you hover or select one it straightens and lifts off the board, the way you'd pull a ticket off a real board to read it.
- **Three fonts, three jobs:**
  - *Special Elite* (typewriter) for anything printed or official: ticket numbers, item codes, check numbers, the cash register
  - *Caveat* (handwriting) for anything a person "says" or jots: agent speech bubbles, ticket notes, the desk log, the run summaries
  - *Playfair Display* for headings and nameplates; *Source Sans* for UI controls so buttons stay crisp and legible

  The split tells you at a glance whether you're reading a **fact** (typed) or a **thought** (handwritten).
- **Warm palette:** cream paper, cork brown, walnut wood, brass nameplates. The only saturated colors belong to the agents, the stamps, and the money, so they stand out.

## How the agents read differently

Each agent is a **coworker with a desk**, not a log source:

| Agent | Nameplate | Icon | Ink color | Personality line |
|---|---|---|---|---|
| Boss | Margaret Hale | 🧭 | navy | "Calm, decisive. Sees the whole shop." |
| Inventory | Theo Park | 📦 | olive green | "Counts twice. Knows every aisle." |
| Accounting | Priya Desai | 🧮 | teal | "Precise to the cent. Nothing leaves without a signature." |
| Facilities | Gus Moreno | 🔑 | rust | "Keeps the lights on and the landlord happy." |
| Customer Service | Bea Lindqvist | 💬 | rose | "Warm, upbeat, a little Bulldog spirit." |

- **Brass nameplates** with a name and a role. A name makes "Priya is checking the cash drawer" feel like a colleague at work, not "agent=accounting kind=tool_call".
- **Each agent's color runs through everything it touches:** the band on top of its desk, its avatar ring, the tint behind its speech bubble, its hand-off chips, its lines in the desk log, and its index card in the report. You can follow Accounting through a run just by following teal.
- **They talk in their own voice when idle.** The Boss: "Desk is quiet. Pick a ticket and I will route it." Inventory: "Aisles A through D, all counted." Customer Service: "Ready to make somebody's day!"
- **Status lamp** on every desk:
  - gray: at desk
  - pulsing amber: thinking or working
  - pulsing blue: waiting on a teammate
  - green: done
  - red: stuck
- **Live speech bubbles** turn raw MCP calls into plain words in the agent's voice. `check_stock_and_price` becomes *"Counting CC-HOOD-NAVY · size M"*, `prepare_payment` becomes *"Drafting an invoice #501 payment for your signature"*, and a hand-off becomes *"Asking Accounting and Inventory…"* with colored chips pointing to the teammate. Three bouncing dots appear while a model call is in flight.
- **The active desk lifts and glows** in the agent's color, with a pulsing ring around the avatar, so your eye goes straight to whoever is working right now.
- **Desks that weren't called stay quiet.** During a run they say "Standing by in case I'm called…". Afterward they dim and say "Not needed on this ticket." This makes it easy to see when the team pulled in more people than the ticket needed, which is exactly what I want to compare against my plan in `desk_tickets.html`.

## How a run unfolds on screen

1. Click **Send to the team →** on a ticket. Its stamp changes to an amber, pulsing **TEAM ON IT**, and the Boss's desk lights up.
2. The board pulls new events every 1.2 s. Each desk's bubble, lamp, and tool chips update as the audit trail grows.
3. The **Desk log** is a lined notebook with a red margin. Every step is written in by hand, indented by how deep in the delegation chain it happened ("Boss → Accounting: …" is one level in, "Accounting → Inventory: …" two). It auto-scrolls inside the notebook only, so the page never jumps under you.
4. When the run ends, a toast slides in ("Ticket 103 resolved by the team, with 1 item for your signature") and the run report fills in.

## How resolved tickets show up

- **A red rubber stamp.** When the team finishes a ticket, a **RESOLVED** stamp slams onto the paper ticket: it scales down from 2.4× and rotates into place with a little bounce, in red ink with `mix-blend-mode: multiply` so it looks inked *into* the paper. Open tickets carry a faint navy **OPEN** stamp.
- **The truth is still printed underneath.** Under the stamp, the ticket's typed footer shows the real database status (`waiting on approval`, `resolved`) and an amber note such as *"1 awaiting your signature"*. "Resolved" means the team finished its part. It never hides a payment you still have to decide on.
- **The latest ticket note** (written by the agents or by your approval) shows in handwriting on the ticket itself. For example, after you sign the rent: *"resolved: request #1: Paid rent for lease 1…"*.
- **"Who did what" report.** It opens with a memo from Margaret Hale (summary, cash position, "I need you to decide"), then one lined **index card per agent** with:
  - what that agent concluded
  - who asked it, and who it asked
  - tools used with counts (e.g. `cash & bills ×2`)
  - any payment or restock it drafted
  - for Customer Service, the draft reply to the customer

  The header shows run time, model calls, tool calls, and tokens, so the cost of a run is never hidden.

## How cash shows up

- **A cash register, not a number in a card.** Dark green housing with a glowing green register display in typewriter digits. It's the one dark object on a warm desk, so it reads as *the* important number.
- **It visibly drops.** When you sign a payment, the balance counts down over about a second (eased), flashes red, and a **−$2,400.00** tag floats up beside it. You *feel* money leave the drawer. (On first load it appears instantly, so it never looks like money vanished just because the page opened.)
- **It looks ahead.** A bar under the display shows the balance, a striped amber section for what's waiting for your signature, and a gold tick at the **$500 cushion**. Below it, "Waiting for your signature" and "If you sign everything" are spelled out, and if that would go under the cushion, a handwritten warning appears: *"That would dip under the $500 cushion. Sign what matters most first."*

## How approvals feel

- Every payment or restock the agents prepare appears as a **printed check** on pale green security-pattern paper:
  - check number
  - "Pay to" (the real payee from the database: Elm City Properties, Bulldog Print Co)
  - the amount in a box
  - a memo line (Rent · lease #1 · ticket 102)
  - the agent's reason in handwriting
  - "drafted by 🧮 Accounting" in that agent's color
- **You sign it.** A "Signing as" line takes your name in handwriting, and the buttons read **Sign & pay**, **Sign & order**, or **Void**. They stay disabled until you've typed a name, because the backend refuses anonymous or agent approvals and the UI makes that rule physical. The name is remembered in the browser.
- Signed and voided checks fold into a small history ("✔ Rent · lease #1, $2,400.00, approved by …").
- **Agents can only draft; only this tray moves money.** The visual metaphor (agents hand you checks, you sign) matches the real guardrail in the backend.

## Small things that make it pleasant to sit at

- **Shop date as a desk calendar** (red top band) from the database, so it's always clear the shop lives on 2026-08-31, not today's date.
- **Connection lamp** in the top bar: "Team ready", "Team on ticket 103", or a red "Backend offline" with a banner that tells you exactly how to start the backend.
- **↺ Fresh day** button resets the database (with a confirm), for trying a ticket again from scratch.
- **Toasts as sticky notes**, slightly rotated, in green (good), yellow (info), or red (problem).
- **Keyboard and screen readers:** tickets are focusable buttons (Enter/Space selects), the live desk bubbles use `aria-live`, and every region has a label. **`prefers-reduced-motion`** turns off all the stamps, pulses, and count-downs.
- **No extra libraries.** Plain React + CSS, with all textures drawn in CSS/SVG, so the desk loads instantly and needs nothing from the network except the backend and Google Fonts (which fall back to system cursive and monospace).

## Why this matters for the people using it

AI agents are invisible by default: they're API calls and JSON. If the owner can't *see* who is working on what, they can't trust the team or catch it overreaching. Giving each agent a face, a voice, and a color makes the delegation visible and easy to judge at a glance. For example, "why is Customer Service on a rent ticket?" Putting money on the right as checks you physically sign makes the human-in-the-loop rule obvious instead of buried in a setting. And making the desk warm and a little playful (stamps, pins, handwriting) makes it a place you're happy to come back to every morning, which is the point of a front desk.
