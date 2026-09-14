"""Roles that have been found but not yet announced, tracked per channel.

The ordering bug this exists to fix: `run.py update` used to fetch, write every
artifact, and fire the Discord/email alerts — and only THEN did the workflow
commit and push. So a run whose push failed had already told subscribers about
roles that were nowhere on the site, and the next run, seeing them as new all
over again, told them a second time.

Splitting it in two fixes both halves at once:

    update  -> writes the data AND queues the new role ids here
    (commit & push — the alerts' precondition)
    notify  -> drains the queue and actually sends

Because the queue is a committed file, a failed push leaves it un-drained: the
roles stay pending and go out with the next successful publish, exactly once.

The queue is keyed BY CHANNEL. With one shared list, a run where Discord
delivered but Telegram timed out had no good move: draining lost the Telegram
alert, and not draining re-sent the Discord one. Each channel now owns its own
pending list and drains only what it actually delivered, so a failure in one
never duplicates or drops the other.
"""

from __future__ import annotations

import json
import os

from . import paths

# Operational warning threshold only. Pending alerts are durable work and must
# never be truncated merely because delivery has been unavailable for a while.
_MAX_PENDING = 200

# Every channel that announces individual roles. The email digest is NOT here:
# it is driven by the store's own news window and its own per-role sent list,
# not by this queue.
CHANNELS = ("discord", "telegram")


class OutboxStateCorrupt(RuntimeError):
    """The durable announcement queue exists but cannot be trusted."""


def _read() -> dict[str, list[str]]:
    """The raw per-channel queues, migrating the old single-list format.

    Older files held {"pending": ["id", ...]} from when Discord was the only
    channel. Those ids were queued but never delivered anywhere else, so every
    channel inherits them — dropping them would silently lose announcements
    across the upgrade.
    """
    if not os.path.exists(paths.OUTBOX_PATH):
        return {c: [] for c in CHANNELS}
    try:
        with open(paths.OUTBOX_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        raise OutboxStateCorrupt(
            f"{paths.OUTBOX_PATH} is unreadable: {exc}"
        ) from exc
    if not isinstance(data, dict) or "pending" not in data:
        raise OutboxStateCorrupt("outbox must be an object with a pending queue")
    pending = data.get("pending") if isinstance(data, dict) else None
    if isinstance(pending, list):  # legacy shape
        if not all(isinstance(value, str) and value for value in pending):
            raise OutboxStateCorrupt("legacy pending queue must contain role ids")
        shared = list(pending)
        return {c: list(shared) for c in CHANNELS}
    if isinstance(pending, dict):
        queues: dict[str, list[str]] = {}
        for channel in CHANNELS:
            values = pending.get(channel, [])
            if not isinstance(values, list) or not all(
                isinstance(value, str) and value for value in values
            ):
                raise OutboxStateCorrupt(
                    f"pending.{channel} must be a list of role ids"
                )
            queues[channel] = list(values)
        return queues
    raise OutboxStateCorrupt("pending must be a list or per-channel object")


def _write(queues: dict[str, list[str]]) -> None:
    os.makedirs(os.path.dirname(paths.OUTBOX_PATH), exist_ok=True)
    tmp = f"{paths.OUTBOX_PATH}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"pending": {c: queues.get(c, []) for c in CHANNELS}},
                  f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, paths.OUTBOX_PATH)


def load(channel: str | None = None) -> list[str]:
    """Ids waiting for `channel`, or the union across channels when omitted."""
    queues = _read()
    if channel is not None:
        return queues.get(channel, [])
    seen: list[str] = []
    known: set[str] = set()
    for c in CHANNELS:
        for jid in queues[c]:
            if jid not in known:
                known.add(jid)
                seen.append(jid)
    return seen


def queue(new_ids: list[str]) -> list[str]:
    """Add this run's new roles to every channel; returns the pending union.

    Duplicate-safe: a role already waiting is not queued twice, so re-running
    `update` before a successful publish doesn't multiply the announcement.
    """
    queues = _read()
    for channel in CHANNELS:
        known = set(queues[channel])
        for jid in new_ids:
            if jid not in known:
                known.add(jid)
                queues[channel].append(jid)
    _write(queues)
    return load()


def drain(done: list[str] | None = None, channel: str | None = None) -> list[str]:
    """Remove `done` from `channel`'s queue; returns what's still pending there.

    Partial on purpose. A run that announced 50 of 60 roles, or whose second
    Discord chunk failed, must keep the rest queued — clearing the whole queue
    on any success is how the unannounced ones would vanish for good. Passing
    no `done` clears that channel entirely; passing no `channel` applies to
    every channel (used only when there is nothing left to deliver anywhere).
    """
    queues = _read()
    targets = [channel] if channel is not None else list(CHANNELS)
    for c in targets:
        if done is None:
            queues[c] = []
        else:
            finished = set(done)
            queues[c] = [jid for jid in queues[c] if jid not in finished]
    _write(queues)
    return queues[channel] if channel is not None else load()
