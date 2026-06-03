"""ONE-TIME SETUP — run this once, then reuse the IDs it saves.

Creates (or updates) the shared environment and the two agents defined in
`agents_config.py`, and writes their IDs to `.agents.json`. `run.py` reads that
file every time it starts a session.

This is the "create once" half of the mandatory Managed Agents flow:

    setup_agents.py  (once)        run.py  (every task)
    ----------------------         --------------------
    environments.create()    -->   sessions.create(agent=ID, environment_id=ID)
    agents.create()  x2            events.stream() / events.send()

Re-running this script is safe and idempotent: agents already in `.agents.json`
are UPDATED in place (which bumps their version) rather than duplicated. That is
how the versioning model is meant to work — iterate on a prompt without orphaning
agents or breaking sessions already running on an older version.
"""

import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from agents_config import AGENTS, ENVIRONMENT

CONFIG_PATH = Path(__file__).parent / ".agents.json"


def load_config() -> dict:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text())
    return {"environment_id": None, "agents": {}}


def save_config(config: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(config, indent=2) + "\n")


def ensure_environment(client: anthropic.Anthropic, config: dict) -> None:
    if config.get("environment_id"):
        print(f"  environment   : reusing {config['environment_id']}")
        return
    try:
        env = client.beta.environments.create(**ENVIRONMENT)
    except anthropic.APIStatusError as e:
        # 409 => an environment with this name already exists (names are unique).
        # Look it up and reuse it instead of failing.
        if e.status_code == 409:
            match = next(
                (e for e in client.beta.environments.list()
                 if e.name == ENVIRONMENT["name"]),
                None,
            )
            if match is None:
                raise
            config["environment_id"] = match.id
            print(f"  environment   : reusing existing {match.id}")
            return
        raise
    config["environment_id"] = env.id
    print(f"  environment   : created {env.id}")


def ensure_agent(client: anthropic.Anthropic, config: dict, key: str, definition: dict) -> None:
    existing = config["agents"].get(key)
    if existing and existing.get("id"):
        # Update in place -> new version. Existing sessions keep their pinned version.
        agent = client.beta.agents.update(existing["id"], **definition)
        action = f"updated -> v{agent.version}"
    else:
        agent = client.beta.agents.create(**definition)
        action = "created"
    config["agents"][key] = {"id": agent.id, "version": agent.version}
    print(f"  {key:<13} : {action} ({agent.id})")


def main() -> None:
    load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in.")

    client = anthropic.Anthropic()
    config = load_config()

    print("Setting up Managed Agents...")
    ensure_environment(client, config)
    for key, definition in AGENTS.items():
        ensure_agent(client, config, key, definition)

    save_config(config)
    print(f"\nSaved IDs to {CONFIG_PATH.name}. You can now run, e.g.:")
    print('  python run.py reviewer "Review this project for issues"')


if __name__ == "__main__":
    main()
