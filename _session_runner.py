"""Shared helper: send a kickoff message to a session and stream the agent's work.

This implements the documented Managed Agents client patterns:
  * stream-first ordering (open the stream before sending the kickoff),
  * the correct idle-break gate (don't break on every `status_idle`),
  * downloading whatever the agent wrote to /mnt/session/outputs/.

These agents use only the built-in server-side toolset (no custom client-side
tools), so there is no `user.custom_tool_result` round-trip to handle here. If you
later add a `{"type": "custom", ...}` tool to an agent, you'd handle its
`agent.custom_tool_use` event in this loop and reply with `user.custom_tool_result`.
"""

import time
from pathlib import Path

import anthropic

BETA = ["managed-agents-2026-04-01"]


def _print_block(block) -> None:
    if getattr(block, "type", None) == "text":
        print(block.text, end="", flush=True)


def run_session(client: anthropic.Anthropic, session_id: str, kickoff_text: str) -> None:
    """Stream one task to completion. Blocks until the session is idle/terminated."""
    console_url = f"https://platform.claude.com/workspaces/default/sessions/{session_id}"
    print(f"\nWatch live in Console: {console_url}\n" + "-" * 72)

    usage = {"input": 0, "output": 0, "cache_read": 0}

    # Stream-first: open the stream, THEN send the kickoff, so we don't miss early
    # events emitted before the consumer attaches.
    with client.beta.sessions.events.stream(session_id=session_id) as stream:
        client.beta.sessions.events.send(
            session_id=session_id,
            events=[{"type": "user.message",
                     "content": [{"type": "text", "text": kickoff_text}]}],
        )

        for event in stream:
            etype = event.type

            if etype == "agent.message":
                for block in event.content:
                    _print_block(block)
                print()  # newline after each agent message

            elif etype == "agent.tool_use":
                print(f"  [tool] {getattr(event, 'name', '?')}", flush=True)

            elif etype == "agent.thread_context_compacted":
                print("  [context compacted]", flush=True)

            elif etype == "session.error":
                err = getattr(event, "error", event)
                print(f"\n  [session error] {err}", flush=True)

            elif etype == "span.model_request_end":
                mu = getattr(event, "model_usage", None)
                if mu:
                    usage["input"] += getattr(mu, "input_tokens", 0) or 0
                    usage["output"] += getattr(mu, "output_tokens", 0) or 0
                    usage["cache_read"] += getattr(mu, "cache_read_input_tokens", 0) or 0

            elif etype == "session.status_terminated":
                print("\n" + "-" * 72 + "\n[session terminated]")
                break

            elif etype == "session.status_idle":
                # IMPORTANT: idle is transient. The session goes idle between parallel
                # tool calls and while waiting on us. Only stop when the stop_reason is
                # terminal — `requires_action` means the agent is waiting on the client.
                stop_reason = getattr(event, "stop_reason", None)
                reason_type = getattr(stop_reason, "type", None)
                if reason_type == "requires_action":
                    # No custom tools here, so nothing to do — keep streaming. (If you
                    # add custom tools, handle their results before continuing.)
                    continue
                print("\n" + "-" * 72 + f"\n[done — {reason_type or 'idle'}]")
                break

    print(
        f"Tokens — input: {usage['input']:,}  output: {usage['output']:,}  "
        f"cache read: {usage['cache_read']:,}"
    )
    _download_outputs(client, session_id)


def _download_outputs(client: anthropic.Anthropic, session_id: str) -> None:
    """Download anything the agent wrote to /mnt/session/outputs/ into ./outputs/<id>/."""
    files = []
    for attempt in range(3):  # brief indexing lag (~1-3s) after the session goes idle
        page = client.beta.files.list(scope_id=session_id, betas=BETA)
        files = list(page.data)
        if files:
            break
        time.sleep(1.5)

    if not files:
        print("No output files written to /mnt/session/outputs/.")
        return

    out_dir = Path(__file__).parent / "outputs" / session_id
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {len(files)} output file(s) to {out_dir}:")
    for f in files:
        content = client.beta.files.download(f.id)
        content.write_to_file(out_dir / f.filename)
        print(f"  {f.filename} ({f.size_bytes:,} bytes)")
