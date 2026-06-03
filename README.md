# Managed Agents Starter — Reviewer + Test Writer

A minimal, runnable project for Anthropic [Managed Agents](https://platform.claude.com/docs/en/managed-agents/overview).
It registers two reusable agents — a **code reviewer** and a **test writer** — and
gives you a CLI to run either one against this project or any other repo.

## Mental model (read this first)

A Managed Agent is **not** code in a repo. When you create one, Anthropic persists a
versioned config object (model + system prompt + tools) on their servers and gives you
back an ID. The agent defines *what kind of worker it is*. A **session** decides *what
it works on this run* — by mounting a GitHub repo or uploading files.

```
agent_test_writer  (created ONCE, lives on Anthropic, referenced by ID)
        │
        ├─ session → mounts github.com/you/project-a  → writes tests for A
        ├─ session → mounts github.com/you/project-b  → writes tests for B
        └─ session → uploads a few local files         → writes tests for those
```

So this is a **control-plane** project: it owns the agent *definitions* and the runner
code. To use the agents on a different codebase you don't copy anything — you just pass
a different repo to a session.

The two halves of the flow map to two scripts:

| Phase | Script | Anthropic calls |
|-------|--------|-----------------|
| **Once** | `setup_agents.py` | `environments.create`, `agents.create` ×2 |
| **Every task** | `run.py` | `sessions.create`, `events.stream`, `events.send` |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # then put your real ANTHROPIC_API_KEY in .env
python setup_agents.py        # creates the env + both agents, saves IDs to .agents.json
```

`setup_agents.py` is idempotent — re-running it *updates* the agents in place (bumping
their version) instead of creating duplicates. Edit the prompts in `agents_config.py`
and re-run to iterate.

## Run

```bash
# Review / test this project itself (mounts its own .py files — works out of the box):
python run.py reviewer    "Review this project for issues"
python run.py test-writer "Write unit tests for the runner logic"

# Point the SAME agents at another repo (set GITHUB_TOKEN in .env first):
python run.py reviewer    --repo https://github.com/you/project-b
python run.py test-writer --repo https://github.com/you/project-b --branch main

# Or hand it specific local files:
python run.py reviewer --files path/to/a.py path/to/b.py
```

Each run prints a **Console URL** so you can watch the session live in the browser,
streams the agent's output to your terminal, prints a token-usage summary, and downloads
anything the agent wrote to `/mnt/session/outputs/` into `./outputs/<session-id>/`
(e.g. the reviewer's `review.md`).

## Files

| File | What it is |
|------|------------|
| `agents_config.py` | The two agent definitions (model, system prompt, tools). The source of truth. |
| `setup_agents.py` | One-time: registers the env + agents, writes `.agents.json`. |
| `run.py` | Per-run: creates a session for an agent and streams it. |
| `_session_runner.py` | Shared SSE streaming loop (stream-first, correct idle gate, output download). |
| `.agents.json` | Generated. Holds your `environment_id` + each agent's `id`/`version`. Gitignored. |

## Where to go next

- **Custom tools** — give an agent a `{"type": "custom", ...}` tool your own code
  handles; then handle its `agent.custom_tool_use` event in `_session_runner.py` and
  reply with `user.custom_tool_result`.
- **Open PRs** — for the test-writer to push a branch and open a PR, mount the repo
  with a write-scoped `GITHUB_TOKEN` and add the GitHub MCP server to the agent.
- **Run tools on your own machine/CI** — switch the environment to `self_hosted` and
  run a worker, so the agent operates on a local checkout instead of a cloud container.
- **Outcomes** — instead of a freeform task, send a `user.define_outcome` with a
  rubric and let the harness iterate until it's satisfied.

See the [overview guide](https://platform.claude.com/docs/en/managed-agents/overview)
for the full picture.
