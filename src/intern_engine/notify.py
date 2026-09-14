"""Discord webhook alerts for newly spotted roles (optional, best-effort).

Set the DISCORD_WEBHOOK_URL secret and every run posts the roles it just found
to that channel. Unset = silent no-op, like every optional integration here.
Failures are swallowed: alerting must never break the data pipeline.
"""

from __future__ import annotations

import os

import httpx

from . import config, grouping, sponsorship

_MAX_EMBEDS = 10   # Discord's cap per message
_MAX_MESSAGES = 5  # up to 50 roles per run; beyond that the channel is spam

# One color per configured cycle, in order (green, orange, purple, blue);
# anything else gets Discord blurple.
_PALETTE = (0x2ECC71, 0xE67E22, 0x9B59B6, 0x3498DB)


def _cycle_colors() -> dict[str, int]:
    labels = config.cycles(config.load_config())
    return {label: _PALETTE[i % len(_PALETTE)] for i, label in enumerate(labels)}


def _embed(record: dict, colors: dict[str, int]) -> dict:
    flag = sponsorship.flag(record.get("sponsorship"))
    title = f"{record.get('company', '')} — {record.get('title', '')}"
    openings = record.get("openings") or 1
    bits = [f"{openings} openings"] if openings > 1 else []
    bits += [record.get("season") or "", record.get("location") or ""]
    if record.get("salary"):
        bits.append(record["salary"])
    if flag:
        bits.append(flag)
    return {
        "title": title[:256],
        "url": record.get("url") or None,
        "description": " · ".join(b for b in bits if b)[:2048],
        "color": colors.get(record.get("season", ""), 0x5865F2),
    }


def send_new_roles(store_data: dict, new_ids: list[str]) -> list[str]:
    """Post new roles to Discord. Returns the ids that no longer need announcing.

    The return value is what the caller drains from the outbox, so it has to be
    exact. Three cases are all "done" without a message going out: no webhook
    configured, an id that's no longer in the store, and a role that has since
    closed — none of those will ever be announceable, so holding them forever
    would just grow the queue.

    A role we MEANT to announce but didn't (a failed chunk, or an overflow past
    the per-run ceiling) is deliberately NOT returned: it stays queued and goes
    out on the next run rather than being silently dropped.
    """
    webhook = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook:
        return list(new_ids)  # nothing to deliver to; don't accumulate
    if not new_ids:
        return []

    live = [(jid, store_data[jid]) for jid in new_ids if jid in store_data]
    settled = [jid for jid in new_ids if jid not in store_data]
    settled += [jid for jid, r in live if not r.get("is_open")]
    records = [(jid, r) for jid, r in live if r.get("is_open")]
    if not records:
        return settled

    colors = _cycle_colors()
    # An employer that opened the same job three times produced three identical
    # embeds. Collapse them into one that says "3 openings"; every id still
    # settles together when that embed lands.
    grouped = [
        (row.get("id") or "", row)
        for row in grouping.group([{**r, "id": jid} for jid, r in records])
    ]
    total = sum(len(r.get("opening_ids") or [1]) for _jid, r in grouped)
    # Discord caps a message at 10 embeds. One message meant role 11+ of a big
    # drop day silently never reached the channel — chunk instead, up to a
    # sane per-run ceiling; the remainder stays queued for the next run.
    shown = grouped[:_MAX_EMBEDS * _MAX_MESSAGES]
    held = sum(len(r.get("opening_ids") or [1]) for _jid, r in grouped[len(shown):])

    def ids_of(chunk) -> list[str]:
        return [
            i for jid, r in chunk
            for i in (r.get("opening_ids") or [jid]) if i
        ]

    chunks = [shown[i:i + _MAX_EMBEDS] for i in range(0, len(shown), _MAX_EMBEDS)]

    announced: list[str] = []
    try:
        for i, chunk in enumerate(chunks):
            if i == 0:
                content = (f"**{total} new internship"
                           f"{'s' if total != 1 else ''} spotted**")
                if held > 0:
                    content += f" (showing {total - held}, {held} in the next batch)"
            else:
                content = f"…continued ({i + 1}/{len(chunks)})"
            httpx.post(
                webhook,
                json={"content": content,
                      "embeds": [_embed(r, colors) for _jid, r in chunk]},
                timeout=10,
            ).raise_for_status()
            announced += ids_of(chunk)  # only after it landed
    except Exception:  # noqa: BLE001 — alerting is a side channel, never fatal
        pass
    return settled + announced
