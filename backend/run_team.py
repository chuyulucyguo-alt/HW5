"""Command-line runner for the agent team.

    python backend/run_team.py "Work through today's open tickets."
    python backend/run_team.py --entry customer_service "Handle ticket 101."
    python backend/run_team.py --db path/to/copy.db "..."   # run against another copy of the database
"""

import argparse
import asyncio
import os
from pathlib import Path
from typing import get_args

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

from agents import run_team  # noqa: E402
from models import AgentName  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the Campus Customs agent team.")
    parser.add_argument("message")
    parser.add_argument("--entry", choices=get_args(AgentName), default="boss")
    parser.add_argument("--db", type=Path, help="database file (default: data/campus_customs_new.db)")
    parser.add_argument("--out", type=Path, help="also save the full result as JSON here")
    args = parser.parse_args()

    result = asyncio.run(run_team(args.message, entry=args.entry, db_path=args.db))
    text = result.model_dump_json(indent=2)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n")


if __name__ == "__main__":
    main()
