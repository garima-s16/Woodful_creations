"""Family 11 - mention detection.

A comment (task or order) can @mention a user by username - e.g.
"@priya can you check this before Friday". Detected mentions become a
real notification to that specific user (never a broadcast, since a
mention is inherently addressed to one person), via the same
NotificationService.notify() every other notification in this app goes
through - not a separate mention-delivery mechanism.

Deliberately server-side only: matching is done directly against the
Users table and never returns candidate/matched users to the caller, so
this can't be used to enumerate usernames (User listing is already
master-only - see users.py) or leak whether a given username exists.
"""
import re
from typing import List

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.notification_service import NotificationService

# Word characters plus dot/underscore/hyphen, matching the character set
# usernames are actually created with in this app (see UserCreate) -
# not an open-ended email-like pattern that could match sentence
# punctuation as part of a "name".
_MENTION_PATTERN = re.compile(r"@([A-Za-z0-9_.-]{2,50})")


def extract_mentioned_usernames(text: str) -> List[str]:
    """Case-preserving raw @handles found in the text - deduplicated,
    order preserved. Matching against real accounts happens later, in
    notify_mentions, so this alone never confirms a username exists."""
    seen = []
    for handle in _MENTION_PATTERN.findall(text or ""):
        if handle.lower() not in [s.lower() for s in seen]:
            seen.append(handle)
    return seen


def notify_mentions(db: Session, *, text: str, comment_id: int, source_type: str, entity_type: str,
                     entity_id: int, title: str, action_path: str, excluded_user_id=None) -> int:
    """Resolves @handles in `text` against real, active User accounts
    and fires one MENTION-type notification per match - dedup_key keyed
    on the specific comment + user, so editing/re-fetching a comment
    (or this being called more than once for the same comment) never
    double-notifies the same person for the same mention.
    excluded_user_id skips notifying someone about their own comment
    (e.g. self-mentioning, or replying in a thread where their own
    username appears quoted)."""
    handles = extract_mentioned_usernames(text)
    if not handles:
        return 0
    notified = 0
    for handle in handles:
        user = db.query(User).filter(User.username.ilike(handle), User.is_active.is_(True)).first()
        if not user or user.id == excluded_user_id:
            continue
        NotificationService.notify(
            db, notification_type="MENTION", severity="INFO",
            title=title, message=f"You were mentioned: \"{text[:200]}\"",
            recipient_user_id=user.id, related_entity_type=entity_type, related_entity_id=entity_id,
            action_path=action_path, dedup_key=f"mention:{source_type}:{comment_id}:user:{user.id}",
        )
        notified += 1
    return notified
