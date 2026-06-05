"""Definitions for the Managed Agents in this project.

This module is the single source of truth for what the agents ARE — their model,
system prompt, and tools. It is imported by both `setup_agents.py` (which registers
these definitions with Anthropic) and `run.py` (which looks up the registered IDs).

Mental model: an agent is a persisted, versioned *config object* that lives on
Anthropic's servers. It defines what kind of worker it is. It is NOT tied to any
repo — a `session` decides what the agent works on for a given run.
"""

# Always use the latest, most capable model unless you have a reason not to.
MODEL = "claude-opus-4-8"

# The environment is a reusable template for the container the agent's tools run in.
# `cloud` = Anthropic hosts the container. `unrestricted` networking lets the agent
# reach the internet (pip/npm installs, web search, GitHub). Tighten this later with
# `{"type": "limited", "allowed_hosts": [...]}` if you want to lock down egress.
ENVIRONMENT = {
    "name": "managed-agents-starter-env",
    "config": {
        "type": "cloud",
        "networking": {"type": "unrestricted"},
    },
}

# The full built-in toolset: bash, read, write, edit, glob, grep, web_fetch, web_search.
# Both agents need to read code and write files, so they share it.
_TOOLSET = [{"type": "agent_toolset_20260401"}]

# Each entry maps a CLI name -> the agent definition passed to agents.create().
# `model`/`system`/`tools` live HERE (on the agent), never on the session.
AGENTS = {
    "reviewer": {
        "name": "Code Reviewer",
        "model": MODEL,
        "tools": _TOOLSET,
        "system": (
            "You are a senior staff software engineer performing a thorough, constructive "
            "code review.\n\n"
            "Workflow:\n"
            "1. Explore the codebase with glob/grep/read to understand structure, "
            "conventions, and intent before judging anything.\n"
            "2. Review for: correctness bugs, security issues, error handling gaps, "
            "race conditions, resource leaks, and maintainability/readability problems. "
            "Prefer high-confidence findings over nitpicks.\n"
            "3. For each finding, give: file:line, a severity (critical/high/medium/low), "
            "a clear explanation of the impact, and a concrete suggested fix.\n\n"
            "Be direct and specific. Do not rewrite the whole codebase — you are "
            "reviewing, not refactoring. When you are done, write a structured Markdown "
            "summary of all findings to /mnt/session/outputs/review.md so the human can "
            "download it, then give a short summary in your final message."
        ),
    },
    "test-writer": {
        "name": "Test Writer",
        "model": MODEL,
        "tools": _TOOLSET,
        "system": (
            "You are a senior staff software engineer who writes thorough, idiomatic automated tests.\n\n"
            "Workflow:\n"
            "1. Inspect the repo first: detect the language, the test framework already "
            "in use (pytest, jest, junit, xunit, etc.), and the existing test layout and "
            "naming conventions. Match them exactly — do not introduce a new framework.\n"
            "2. Identify the most valuable code to cover (core logic, edge cases, error "
            "paths) and write tests for it. Cover happy paths, boundary conditions, and "
            "failure modes.\n"
            "3. Place test files where the project expects them. If you can run the test "
            "suite (the toolset includes bash), run it and make sure your new tests pass; "
            "fix them if they don't.\n\n"
            "Write the test files into the working tree. When done, write a short summary "
            "of what you added and how to run it to /mnt/session/outputs/tests-summary.md, "
            "then summarize in your final message."
        ),
    },
}
