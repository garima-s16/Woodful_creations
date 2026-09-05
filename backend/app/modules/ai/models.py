from sqlalchemy import Column, String, Text, Integer
from app.platform.database.base import BaseModel


class ChatLearningCandidate(BaseModel):
    """A controlled learning mechanism for
    the deterministic chatbot, NOT self-modifying code. When Gemini
    successfully interprets a message the deterministic parser could
    not (chat_service.py's own keyword/pattern matching found nothing),
    a candidate row is created here: the user's phrase and the tool
    name Gemini resolved it to (a proxy for "intent" - the same tool
    names already defined in ai_gateway.py's READ_TOOLS/WRITE_TOOLS,
    never a new, arbitrary category).

    This is deliberately NOT an active rule by default. Only once a
    master explicitly approves a candidate (status -> "approved") does
    chat_service.py's deterministic parser consult it, as one more
    normalized-phrase lookup alongside its existing keyword lists -
    never as generated/executed code, never as a change to
    authorization or business rules.

    Deliberately stores only the phrase and the resolved tool name -
    never amounts, IDs, phone numbers, or other business data - to
    prefer generic language patterns; persisting an
    entire sensitive conversation is not required. A user could in
    principle type sensitive text as part of a free-text message; this
    table does not attempt to detect and strip that, so it must stay
    master-only-readable, matching every other admin-only surface in
    this codebase, and a master reviewing/approving a candidate can
    reject or edit it before approval reaches the active list.
    """
    __tablename__ = "chat_learning_candidates"

    phrase = Column(String(500), nullable=False, index=True)
    normalized_phrase = Column(String(500), nullable=False, index=True)
    resolved_tool = Column(String(100), nullable=False)
    status = Column(String(20), nullable=False, default="pending")  # pending / approved / rejected
    occurrence_count = Column(Integer, nullable=False, default=1)  # how many times this exact normalized phrase produced this tool
    reviewed_by = Column(String(255), nullable=True)
    review_notes = Column(Text, nullable=True)
