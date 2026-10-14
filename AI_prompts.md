# AI Prompt Log

## Problem 1: Vibe coder prompts

**Prompt:** Today we're working on HW 5, so save all the work in the HW 5 folder. Create `AI_prompts.md` in HW 5 at the start of the assignment and keep it updated as I work.

**Follow-up:** Give every problem its own section headed with its number and title. Under it, log at least one prompt I typed, paraphrased in my voice, and add a follow-up only when I actually needed one, with one sentence on what the first try didn't cover. The first version didn't lay out this per-problem structure.

## Problem 2: Study the Campus Customs database

**Prompt:** Unzip the data folder from my Downloads into HW 5 and walk me through `data/campus_customs.db`: every table and what its fields mean. Then make a copy called `data/campus_customs_new.db` that we'll change in later problems, and keep the original untouched. Finally, explain the three open tickets and which other tables each one points to.

**Follow-up:** Start `output/harness.md` and, for each table, list its fields with one short line on why the agents need that table. I'll keep adding to this file in later problems. The first round only explained the database in chat and saved nothing to a harness file.

## Problem 3: Build the MCP server

**Prompt:** Using FastMCP, set up an MCP server in `mcp_server/` that reads and writes our working copy, `data/campus_customs_new.db`. All the agents will share it, and we'll add tools later. For now, give it the three tools I'll clearly need for the open tickets, with obvious names. Every answer has to come from the database and nothing can be made up. No need to hook it up to anything or run it yet.

**Follow-up:** In `output/harness.md`, write up each of the three tools on its own: which table(s) it reads, which ticket (101, 102, or 103) it helps with, and one sentence tying that tool to that specific ticket, not something generic like "reads inventory." Also add a short `mcp_server/README.md` covering what the server is for, which database file it uses, and its three tools. The first version only had a general tool table without the table-to-ticket reasoning, and the server folder had no README.

## Problem 4: Add the MCP server to vibe coder and test each tool

**Prompt:** Hook our campus-customs MCP server into you (Claude Code) for this project so you can call its tools directly. Save the connection config as `.mcp.json` at the root of HW 5, pointing at the HW 5 venv's Python and `mcp_server/server.py`.

**Follow-up:** Open a fresh Claude Code session inside HW 5 so it loads `.mcp.json`, then call each tool through MCP (not by running Python): list the open tickets, check stock and price for ticket 101's tee in size S, ticket 103's hoodie in size M, and a fake SKU, and pull the cash and bills. Report each result against what the database says, and save the evidence in `output/mcp_smoke.json`: for each tool, the question I asked, the tool name, and its exact output. The first round only saved the config; this session had started before the file existed, so the tools hadn't been called from the vibe coder and there was no saved proof.

## Problem 5: Build the agent team and grow the MCP tools

**Prompt:** Build a Campus Customs agent team in PydanticAI with five roles: Boss, Inventory, Accounting, Facilities, and Customer Service. Each agent should be able to hand work to any of the others, so include the prompts, data models, and the delegation loop. Put one prompt file per agent in `backend/prompts/`, the types in `backend/models.py`, and the agent code under `backend/`. Every agent must use only gpt-6-luna through my Portkey key. Write the prompts in detail with the shop rules each role needs (what it owns, what it must never do, and when it needs my approval), and add whatever MCP tools the team needs to actually work the tickets.

**Follow-up:** Add whatever MCP tools the agents still need for the open tickets. All shop facts must come through the MCP server over `data/campus_customs_new.db`, with no side path around it. Make every agent-loop step append an entry to `output/audit_trail.json` with enough detail to audit later, and never wipe it between runs. In `output/harness.md`, list each agent and each MCP tool with the tables it uses, and add a short safety section on the guardrails a real shop would want once agents touch real customers and money, plus the limits that keep token use under control. Bring `mcp_server/README.md` in line with the current tool list. The first version had no audit trail, so a stuck run gave no clue what it was doing; it also had no safety section, and there were no token or time limits beyond a request cap.

## Problem 6: Plan the three tickets

**Prompt:** Before we hook up the backend, I want to write down what I expect the team to do on each open ticket. Make `output/desk_tickets.html`, a standalone page I can just double-click, with one tab each for tickets 101, 102, and 103, plus Cash and Reflection tabs that only say "coming later" for now. On each ticket tab, fill in an Expected section (the facts the agents should find, who should handle what with which tools, the outcome and approvals I expect, and what must not happen) and leave an empty Actual section to fill in after I run the agents.

**Follow-up:** Make each Expected section more specific, in my own words: who the Boss should call first and why, every hand-off I expect between agents in order (not "Boss calls everyone"), and which MCP tools each agent should use in that run. Also say who should *not* be called and which tools shouldn't be touched, so I can compare the plan with what really happens. The first version had a single generic flow per ticket that pulled in almost every specialist, with no reason for who goes first.

## Problem 7: Backend routes

**Prompt:** Build the FastAPI backend in `backend/main.py` that my React dashboard will call next. I need routes to:
- list the three tickets and whether each is open or resolved
- run the agent team on one ticket by id
- return the latest agent events (what each agent said and which tools it called) so the board can refresh
- show the current checking balance from `cash_accounts`
- reset the database back to the original so I can try again from scratch

Money is the important part: the agents should only *prepare* a payment or purchase. Cash should change only when a person clicks Approve, through its own route.

**Follow-up:** Start the backend from the `backend/` folder with `uvicorn main:app --reload --port 8000` so the dashboard can reach it at `http://localhost:8000`, and in `output/harness.md` list every route on a single line: its URL and what it does. The first version ran on a different port without auto-reload, and the harness only had a wide route table instead of a quick one-line-per-route list.

## Problem 8: Agent dashboard

**Prompt:** Build the dashboard in `frontend/` with React + Vite + TypeScript, calling the Problem 7 routes. It needs to:
- show all three tickets
- let me pick one and send it to the agent team
- show each agent and what it's saying or doing while the run happens
- mark the ticket resolved when the run is done
- give a short summary of what each agent did on it
- let me approve a payment or purchase when one is waiting
- show the checking balance, which should drop after I approve a payment

Make it look like a desk someone would actually want to work at. Commit to a shop front desk theme: tickets as paper notes pinned on a corkboard, a desk or nameplate for each agent, warm colors, paper texture, and a handwritten font for notes. Give each agent its own color, icon, and personality (the Boss calm and in charge, Accounting exact).

**Follow-up:** Have the dashboard call the backend directly at `http://localhost:8000`, and on the backend allow the Vite page's origin (`http://localhost:5173`) so the browser can reach the routes; I'll start the board with `npm run dev`. Then write `output/design.md` explaining the look I chose and why: the layout, how the agents read differently from each other, how resolved tickets and cash show up, and the creative touches that make it a desk people would enjoy using. The first version went through a Vite proxy on a different port instead of calling `localhost:8000` with the backend allowing the Vite origin, and none of the design choices were written down.

## Problem 9: Resolve the tickets

**Prompt:** Reset `data/campus_customs_new.db` one more time so the full test starts clean, and write down the starting checking balance. Then, from the board, run tickets 101, 102, and 103 one after another until each one shows as resolved. After that, open `output/desk_tickets.html` and fill in the Actual section on every ticket tab from this run: which agents got involved, who handed work to whom, and which tools each one called. Keep the Expected sections as they are so I can compare the two.

**Follow-up:** On the Cash tab of `output/desk_tickets.html`, list the money step by step: the starting checking balance after the reset; for each ticket, how cash changed when it was resolved and why (which payment or purchase, and the dollar amount); and the ending balance, which has to match `cash_accounts` in the working database. Also save `output/resolved_tickets.json` (per ticket: id, final status, short outcome, what each agent did, and any human approvals) and `output/resolved_board.html`, a double-click page with a screenshot of my React board for each resolved ticket. Keep appending the real runs to `output/audit_trail.json`, and finish `output/harness.md` so it covers the tables, MCP tools, the five agents, API routes, dashboard, and safety rules. For the money I signed rent and invoice 501 as Lucy Guo and held the $264 restock. The first pass left every check unsigned, so the Cash tab had nothing to itemize, and the rent check wasn't linked to ticket 102, so paying it wouldn't have closed that ticket.

## Problem 10: Reflection

**Prompt:** Fill in the Reflection tab of `output/desk_tickets.html` with my own answers, citing the ticket tabs and the Cash tab as evidence. Here is what I think:

1. **How the agents did on each ticket.**
   - **101:** The facts were right (0 in size S, invoice 501 overdue) and the customer reply hid costs and vendors. But Accounting prepared rent on its own (out of scope), and Inventory and Accounting were each asked twice. 19 model calls, about 60k tokens.
   - **102:** The best run. It took 35 seconds, and `list_approvals` blocked a duplicate rent request. The one gap was that rent request #1 wasn't linked to ticket 102.
   - **103:** The discount math was exact ($52.20 at 10%, $46.40 at 20%), but Inventory was asked 3 times and the approved discount never reached Customer Service. 23 calls, about 64k tokens.
2. **Actual vs. Expected.**
   - **101:** I expected 3 hand-offs starting with Inventory. Actual was 5, with the Boss calling Customer Service, Inventory, and Accounting in parallel. The outcome matched.
   - **102:** Closest match. The only differences were one extra Boss → Accounting call and the missing ticket link.
   - **103:** I expected Accounting first, then Customer Service with the numbers. Actual was 5 hand-offs in parallel, so the customer reply offered no discount.
3. **What would have been simpler as one agent.** Facilities and Inventory. On 102, Facilities only read lease 1 and handed payment to Accounting; on 101, Inventory only called `get_ticket`. One agent working in order would also have avoided the repeated Inventory questions on 103. Multiple agents were still worth it for separation of duties: only Accounting prepares payments, and Customer Service never shows costs to customers.
4. **Three new problems the team could solve.**
   - CC-TEE-WHITE size M runs out with an overdue Bulldog Print Co invoice, like 101 (`get_ticket`, `list_vendors`, `prepare_payment`).
   - Another club asks for a bulk discount on CC-HOOD-NAVY, like 103 (`quote_bulk_price`, `prepare_purchase`).
   - The next $2,400 rent on lease 1 comes due 2026-10-02, after the payment on the Cash tab (`get_cash_and_bills`, `prepare_payment`).
5. **Three problems it could not solve, and what's needed.**
   - **Sending messages:** Facilities only drafted the landlord note on 102. Needs a `send_email` tool and a Communications agent, with human approval before sending.
   - **Recording sales and receivables:** no hoodie sale was recorded for 103 because there's no orders table. Needs `create_order`, `record_sale`, and `create_invoice` tools and a Sales/AR agent.
   - **Cash shortfalls:** the Cash tab ends at $160, $340 under the $500 cushion, so the $264 restock was held. Needs a `forecast_cash` tool reading `payments` and receivables, and a Treasury agent.

**Follow-up:** Tie every reflection answer to this app and the three tickets we actually ran, citing the ticket tabs and the Cash tab on the same page as evidence (specific delegations, tool calls, replies, dollar amounts), not generic AI-agent talk. Also make the project match the expected file layout: a root `requirements.txt`, `.env.example`, `.gitignore`, `.mcp.json`, and `README.md`; `data/` with both databases; `mcp_server/` with `server.py` and `README.md`; `frontend/`; `backend/` with `main.py`, `models.py`, and the five prompt files; and `output/` with the harness, smoke test, desk page, design notes, resolved tickets and board, audit trail, and `github_url.txt`. The first version of the reflection named the tabs but didn't point to exact evidence on them, and the project was missing the root setup files and `github_url.txt`, used absolute paths in `.mcp.json`, and had extra per-folder requirements files.

## Problem 11: Submit to GitHub

**Prompt:** I'm ready to hand in HW 5. Publish the project to my public repo at https://github.com/chuyulucyguo-alt/HW5 and put that link in `output/github_url.txt`. Before pushing, check that:
- `.gitignore` keeps out my real `.env`, `.venv`, and `node_modules`, but still includes both `.db` files
- `.env.example` only has variable names and no real key
- `requirements.txt` and a root `README.md` exist and the layout matches the assignment
- nothing in the project contains a real API key or any model other than gpt-6-luna

Show me `git status` and the full list of files that would be committed before anything goes up, and only commit and push to `main` after I say OK. Don't reset the database: `campus_customs_new.db` stays in its final state with checking at $160. Add the Problem 10 and 11 entries here first. If the push needs a login or fails, tell me what to do instead of working around it.

**Follow-up:** Make the README walk a grader through running the app in order:
1. Copy the original database over the working copy when you need a clean run.
2. Start the MCP server.
3. Start the FastAPI backend.
4. Start the React board.
5. Reset the database before a full three-ticket run.

The first README only had a quick start (venv, backend, board). It didn't explain the original-vs-working database copy, how the MCP server gets started, or that the database must be reset before running all three tickets.
