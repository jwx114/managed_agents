"""PER-RUN — start a session for one of the agents and stream its work.

Usage:
    python run.py reviewer    "Review this project for issues"
    python run.py test-writer "Write unit tests for the core logic"

    # Point an agent at ANY repo (this is why the agents are reusable):
    python run.py reviewer    --repo https://github.com/you/project-b
    python run.py test-writer --repo https://github.com/you/project-b --branch main

    # Or hand it specific local files:
    python run.py reviewer --files src/auth.py src/db.py

This is the "every task" half of the flow. It does NOT create agents — it loads the
IDs that `setup_agents.py` saved and references them. The agent decides *how* to work;
the session (here) decides *what* it works on, via `resources`.
"""

import argparse
import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from _session_runner import run_session

CONFIG_PATH = Path(__file__).parent / ".agents.json"
PROJECT_ROOT = Path(__file__).parent

DEFAULT_TASK = {
    "reviewer": "Review the mounted code and report your findings.",
    "test-writer": "Write thorough unit tests for the most important logic in the mounted code.",
}


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        sys.exit("No .agents.json found. Run `python setup_agents.py` first.")
    return json.loads(CONFIG_PATH.read_text())


def build_resources(client: anthropic.Anthropic, args) -> list:
    """Decide what the agent operates on this run."""
    if args.repo:
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            sys.exit("--repo needs GITHUB_TOKEN set in your environment / .env.")
        resource = {
            "type": "github_repository",
            "url": args.repo,
            "authorization_token": token,
        }
        if args.branch:
            resource["checkout"] = {"type": "branch", "name": args.branch}
        return [resource]

    if args.files:
        resources = []
        for path in args.files:
            p = Path(path)
            if not p.is_file():
                sys.exit(f"File not found: {path}")
            with open(p, "rb") as fh:
                uploaded = client.beta.files.upload(file=fh)
            resources.append({
                "type": "file",
                "file_id": uploaded.id,
                "mount_path": f"/workspace/{p.name}",
            })
        return resources

    # Default: mount this starter project's own Python files so `run.py` works
    # out of the box with nothing extra to configure.
    resources = []
    for p in sorted(PROJECT_ROOT.glob("*.py")):
        with open(p, "rb") as fh:
            uploaded = client.beta.files.upload(file=fh)
        resources.append({
            "type": "file",
            "file_id": uploaded.id,
            "mount_path": f"/workspace/{p.name}",
        })
    return resources


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a Managed Agent against some code.")
    parser.add_argument("agent", choices=["reviewer", "test-writer"])
    parser.add_argument("task", nargs="?", help="What to do this run (optional).")
    parser.add_argument("--repo", help="GitHub repo URL to mount (needs GITHUB_TOKEN).")
    parser.add_argument("--branch", help="Branch to check out (with --repo).")
    parser.add_argument("--files", nargs="+", help="Local file(s) to upload and review.")
    args = parser.parse_args()

    load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in.")

    config = load_config()
    agent_entry = config["agents"].get(args.agent)
    if not agent_entry:
        sys.exit(f"Agent '{args.agent}' not in .agents.json. Re-run setup_agents.py.")

    client = anthropic.Anthropic()

    resources = build_resources(client, args)
    print(f"Mounting {len(resources)} resource(s); creating session...")

    # The session references the agent by ID. model/system/tools are NOT here —
    # they live on the agent. This is just a pointer + what to work on.
    session = client.beta.sessions.create(
        agent={"type": "agent", "id": agent_entry["id"], "version": agent_entry["version"]},
        environment_id=config["environment_id"],
        title=f"{args.agent} run",
        resources=resources,
    )

    task = args.task or DEFAULT_TASK[args.agent]
    run_session(client, session.id, task)


if __name__ == "__main__":
    main()
