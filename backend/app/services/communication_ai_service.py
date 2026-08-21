"""Family 11 - "AI" communication helpers.

Honesty requirement: this app has no real LLM integration (see
chat_service.py's own docstring - OPENAI_API_KEY exists in config but is
unused). Every function here is plain, deterministic text processing -
keyword/heuristic extraction, not genuine language understanding. Every
result this module returns is labeled "rule-based" so nothing here is
ever presented as real AI reasoning it isn't. If a real LLM integration
is added later, this module's outputs are exactly the kind of thing it
would replace - not a claim this already does it.

None of this sends anything anywhere: summarize/extract/draft are all
read-only analysis of existing comments/activity already stored via the
normal comment/activity endpoints, or a plain string handed back for a
human to review, edit, and send themselves through whatever channel
they already use outside Woodful. There is no external send capability
in this app for this module to call even if it wanted to.
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional


# A line "asks a question" if it ends with '?' - simple and conservative
# on purpose: this flags candidates for a human to check, not a claim
# that the app understands the conversation.
_QUESTION_RE = re.compile(r"\?\s*$")

# Heuristic action-item markers - imperative/commitment language a
# person skimming a thread would themselves look for. Deliberately a
# fixed keyword list, not inferred "intent".
_ACTION_MARKERS = (
    "please", "need to", "needs to", "todo", "to-do", "to do:", "action:", "follow up", "follow-up",
    "can you", "could you", "will send", "will share", "must", "should", "pending", "waiting on", "asap",
)


@dataclass
class CommunicationEntry:
    """One normalized item from any comment/activity source (task
    comment, order comment, client activity) - the common shape every
    function below operates on, regardless of which table it came
    from."""
    author: str
    text: str
    date: object  # datetime - kept loose to avoid importing every source's date type
    source_type: str  # "task_comment" / "order_comment" / "client_activity"


@dataclass
class CommunicationInsights:
    method: str
    summary: str
    action_items: List[str] = field(default_factory=list)
    unanswered_items: List[str] = field(default_factory=list)
    entry_count: int = 0


def summarize_and_extract(entries: List[CommunicationEntry]) -> CommunicationInsights:
    """Extractive summary + action items + unanswered questions - all
    rule-based (see module docstring). Ordered oldest-first before
    processing, so "unanswered" can mean "no later entry from a
    different author follows this question"."""
    ordered = sorted(entries, key=lambda e: e.date)

    if not ordered:
        return CommunicationInsights(
            method="rule_based_extractive", summary="No communication recorded yet.",
            action_items=[], unanswered_items=[], entry_count=0,
        )

    summary_lines = [f"{e.author}: {e.text.strip()[:160]}" for e in ordered[-5:]]
    summary = (
        f"{len(ordered)} entr{'y' if len(ordered) == 1 else 'ies'} recorded. "
        f"Most recent: " + " | ".join(summary_lines)
    )

    action_items = []
    for e in ordered:
        lowered = e.text.lower()
        if any(marker in lowered for marker in _ACTION_MARKERS):
            action_items.append(f"{e.author}: {e.text.strip()[:200]}")

    unanswered_items = []
    for i, e in enumerate(ordered):
        if not _QUESTION_RE.search(e.text.strip()):
            continue
        answered = any(
            later.author != e.author for later in ordered[i + 1:]
        )
        if not answered:
            unanswered_items.append(f"{e.author}: {e.text.strip()[:200]}")

    return CommunicationInsights(
        method="rule_based_extractive", summary=summary, action_items=action_items,
        unanswered_items=unanswered_items, entry_count=len(ordered),
    )


_DRAFT_TEMPLATES = {
    "follow_up": (
        "Hi {name},\n\nFollowing up on {subject}. Let me know if you have any updates or questions "
        "on your end.\n\nThanks,\n{sender}"
    ),
    "status_update": (
        "Hi {name},\n\nA quick update on {subject}: {detail}\n\nHappy to answer any questions.\n\n"
        "Thanks,\n{sender}"
    ),
    "payment_reminder": (
        "Hi {name},\n\nA gentle reminder regarding the outstanding balance on {subject}. "
        "Please let us know if you have any questions about the payment.\n\nThanks,\n{sender}"
    ),
}


def draft_message(purpose: str, *, name: str, subject: str, sender: str, detail: Optional[str] = None) -> str:
    """A plain template fill-in, not generated text - the same honesty
    boundary as summarize_and_extract above. Returned as a draft only:
    nothing in this app sends it anywhere. Per Family 11's explicit
    rule, external communication requires a human to take it from here
    and send it themselves through whatever channel they use outside
    Woodful - this module (and this app) has no send capability to
    bypass that with even if it tried."""
    template = _DRAFT_TEMPLATES.get(purpose)
    if not template:
        raise ValueError(f"Unknown draft purpose: {purpose}")
    return template.format(name=name, subject=subject, sender=sender, detail=detail or "no change since last update")
