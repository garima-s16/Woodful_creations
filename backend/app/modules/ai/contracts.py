"""AI domain contracts: chat request/response/context Pydantic
models and the ChatLearningCandidate DB model (models.py), untrusted-
text sanitization and capability reporting (security.py), and agent
routing/report logic (agents.py). Combines the former models.py,
security.py, and agents.py."""
from sqlalchemy import Column, String, Text, Integer
from app.platform.database import BaseModel
import re
from pydantic import BaseModel as PydanticBaseModel
from typing import List, Optional, Tuple
from enum import Enum
from sqlalchemy.orm import Session


# --- models.py ---
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


DEICTIC_REFERENCE_WORDS = [
    "usme", "usmein", "ismein", "iska", "iski", "iske", "uska", "uski", "uske",
    "it", "that", "this one", "about it", "in it",
]


_DEICTIC_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in DEICTIC_REFERENCE_WORDS) + r")\b"
)


def _has_deictic_reference(message: str) -> bool:
    return bool(_DEICTIC_PATTERN.search(message))


class CartItemContext(PydanticBaseModel):
    """One line of the client-side purchase cart, sent along so the
    assistant can answer questions about it - the cart itself has no
    backend representation at all (see cartSlice.js), so this is the
    only way the server ever finds out what's in it."""
    material_id: int
    quantity: float


class ChatContext(PydanticBaseModel):
    """What the user is currently looking at, so the assistant can answer
    "summarize this order" style questions without the user needing to
    name the record explicitly. All optional - a chat message sent from
    the dashboard or a list page simply omits these.

    record_type/record_id is the current, preferred way to describe this
    - a single generic pair ("order", 14) rather than one dedicated field
    per page type. The five specific *_id fields below are kept for
    backward compatibility with existing frontend call sites and are
    used as a fallback when record_type/record_id aren't sent - new
    frontend code should send the generic pair instead of adding a sixth
    specific field the next time a new page type needs context.

    cart_items is a genuinely different kind of context, not another
    record reference - the assistant can't query the cart from the
    database (it doesn't have one), so this is the frontend handing over
    data the server has no other way to see, not "what record is open"."""
    record_type: Optional[str] = None  # "order" | "material" | "client" | "employee" | "supplier"
    record_id: Optional[int] = None
    cart_items: Optional[List[CartItemContext]] = None

    order_id: Optional[int] = None
    client_id: Optional[int] = None
    material_id: Optional[int] = None
    employee_id: Optional[int] = None
    supplier_id: Optional[int] = None
    # What the assistant last talked about, so "usme kya scene hai" /
    # "what about it" can resolve without the user repeating the name.
    # Same stateless pattern as `pending` below - the frontend echoes
    # back whatever `last_entity` the previous response contained,
    # there is no server-side conversation store. Only used as a
    # fallback, and only when the message actually contains a deictic
    # reference (see resolved_with_reference) - it does not silently
    # apply to unrelated questions.
    last_entity: Optional[dict] = None
    # "HDHMR kitni hai?" -> "And pre
    # laminated?" is an elliptical follow-up (no deictic word for
    # resolved_with_reference to catch - it omits the subject
    # entirely). Unlike last_entity above, this needs no backend
    # semantic judgment about "what was this response about" - the
    # frontend already has both texts directly from its own state (the
    # message it just sent, the reply it just received), so it simply
    # echoes them back. Used only to give Gemini real conversational
    # history (see build_conversation_context) - the deterministic
    # layer's own reference resolution is unaffected by these fields.
    last_user_message: Optional[str] = None
    last_assistant_message: Optional[str] = None
    # Carries a partially-collected action across turns. There is no
    # server-side conversation table - the frontend simply echoes back
    # whatever `clarification` the previous response contained, so a
    # multi-turn "what payment mode?" exchange works statelessly.
    pending: Optional[dict] = None

    def resolved(self):
        """Returns (record_type, record_id) regardless of which form the
        caller used - the one place this normalization happens, so
        _answer_from_context doesn't need a growing if/elif chain over
        five separate fields."""
        if self.record_type and self.record_id:
            return self.record_type, self.record_id
        if self.order_id:
            return "order", self.order_id
        if self.material_id:
            return "material", self.material_id
        if self.client_id:
            return "client", self.client_id
        if self.employee_id:
            return "employee", self.employee_id
        if self.supplier_id:
            return "supplier", self.supplier_id
        return None, None

    def resolved_with_reference(self, message: str):
        """Like resolved(), but additionally falls back to last_entity
        when the current page has no record AND the message contains a
        deictic reference word ("usme", "iska", "it", "that") - so a
        follow-up question can refer to whatever was just discussed
        without the user repeating the name. Never applied otherwise,
        so an unrelated question is never misattributed to the last
        topic."""
        record_type, record_id = self.resolved()
        if record_type and record_id:
            return record_type, record_id
        if self.last_entity and _has_deictic_reference(message.lower()):
            return self.last_entity.get("type"), self.last_entity.get("id")
        return None, None


class ChatRequest(PydanticBaseModel):
    message: str
    context: Optional[ChatContext] = None


class ProposedAction(PydanticBaseModel):
    """A structured, high-impact action the assistant has parsed from the
    conversation but has NOT executed. The frontend shows this for
    explicit user confirmation before calling the real endpoint - the
    assistant never modifies business data on its own. `action_type`
    tells the frontend which confirmation UI/endpoint to use; `payload`
    is the exact request body that endpoint expects."""
    action_type: str
    summary: str
    payload: dict


class ChatResponse(PydanticBaseModel):
    response: str
    suggestions: List[str] = []
    proposed_action: Optional[ProposedAction] = None
    # What to remember for the next turn if the assistant is still
    # collecting information (e.g. has an amount, still needs a payment
    # mode). The frontend must send this back as context.pending on the
    # user's next message - it is never persisted server-side.
    clarification: Optional[dict] = None
    # What this response was about, e.g. {"type": "order", "id": 14} -
    # the frontend echoes this back as context.last_entity on the next
    # message so a deictic follow-up ("usme kya scene hai") can resolve
    # without the user repeating the name. Not persisted server-side.
    last_entity: Optional[dict] = None
    # Structured, clickable results for "which records" style questions
    # (e.g. "which orders have outstanding payments") - each one has
    # enough to render a card and link straight to the real detail page,
    # rather than a wall of text listing them.
    records: List[dict] = []


# --- security.py ---
"""AI Intelligence Layer.

This module does NOT reimplement the chatbot. ChatService.process_message
already is the Intent -> Permission -> Retrieval -> Response pipeline:
- Intent: keyword/regex matching against the incoming message (m = message.lower())
- Permission: user_role is threaded into every handler; get_current_user
  gates the route before any of this runs; sensitive data is redacted
  or refused per-role inside the handlers themselves (never left to the
  frontend to hide)
- Retrieval: every handler queries real SQLAlchemy models - Order,
  Client, Material, Payment, etc. - never a fabricated or cached answer
- Response: plain text assembled from what was actually retrieved

What this module adds is the explicit, honest layer this asks
for: a classification of what's real right now versus what depends on
future infrastructure, and shared guards (untrusted-content handling,
confirmation-required enforcement) that apply across every handler
rather than being reimplemented per-handler.
"""

class CapabilityStatus(str, Enum):
    IMPLEMENTED = "IMPLEMENTED"
    EXTERNAL_SERVICE_DEPENDENT = "EXTERNAL-SERVICE DEPENDENT"
    MOCKED = "MOCKED"
    NOT_VERIFIED = "NOT VERIFIED"


AI_CAPABILITIES = [
    {
        "capability": "Business-data retrieval (orders, payments, stock, clients, employees, suppliers)",
        "status": CapabilityStatus.IMPLEMENTED,
        "detail": "Every chatbot handler queries real database records through SQLAlchemy models. "
                   "Nothing is fabricated or cached - if a query returns nothing, the response says so.",
    },
    {
        "capability": "Role-based access control on AI responses",
        "status": CapabilityStatus.IMPLEMENTED,
        "detail": "user_role is passed into every handler; financial and salary-adjacent handlers "
                   "explicitly check for master and refuse or redact otherwise. This is enforced "
                   "server-side inside chat_service.py, not by the frontend hiding a button.",
    },
    {
        "capability": "Action proposal with required confirmation",
        "status": CapabilityStatus.IMPLEMENTED,
        "detail": "ProposedAction is returned to the frontend but never executed by the assistant. "
                   "The frontend must call the real, authorized endpoint after the user explicitly "
                   "confirms - the chatbot has no code path that writes to the database directly.",
    },
    {
        "capability": "Rate limiting on chat requests",
        "status": CapabilityStatus.IMPLEMENTED,
        "detail": "The /api/chat/ route is rate-limited per settings.RATE_LIMIT_CHAT_PER_MINUTE, "
                   "on top of the global per-IP floor applied to every endpoint.",
    },
    {
        "capability": "Basic Hindi/Hinglish keyword and phrasing recognition",
        "status": CapabilityStatus.IMPLEMENTED,
        "detail": "A fixed set of hand-written Hindi/Hinglish patterns (e.g. 'kitna h', 'ka payment', "
                   "'add kr do') are matched alongside their English equivalents. This is pattern "
                   "matching against a known, limited vocabulary - not general multilingual "
                   "understanding, and it will not generalize to phrasings outside that list.",
    },
    {
        "capability": "Genuine multilingual natural-language understanding",
        "status": CapabilityStatus.NOT_VERIFIED,
        "detail": "No external LLM is connected in this runtime. What exists is deterministic "
                   "keyword/regex matching, which handles a fixed set of known phrasings "
                   "(including some broken/incomplete English and common Hinglish patterns) but "
                   "cannot genuinely parse arbitrary broken text or truly novel phrasing the way "
                   "an LLM would. Claiming otherwise would misrepresent the system.",
    },
    {
        "capability": "Excel/document content understanding (reading and reasoning over uploaded file content)",
        "status": CapabilityStatus.NOT_VERIFIED,
        "detail": "The chatbot can locate and list documents (filename, description, upload date) "
                   "after a permission check, but never opens or parses file content. Purchase-import "
                   "Excel parsing is a separate, non-AI, deterministic column-mapped parser "
                   "(app/modules/procurement/services.py) - it is not part of the chatbot and does not "
                   "'understand' spreadsheets in any general sense.",
    },
    {
        "capability": "Recommendations (next actions, bottlenecks, follow-ups, duplicate detection)",
        "status": CapabilityStatus.IMPLEMENTED,
        "detail": "Computed from real stored data (dates, statuses, thresholds already in the "
                   "database) via explicit rules - e.g. 'next action' is the earliest not-DONE task "
                   "by date. These are genuine derived facts, not LLM-generated suggestions.",
    },
    {
        "capability": "Connecting a real external LLM for genuine NLU/reasoning",
        "status": CapabilityStatus.EXTERNAL_SERVICE_DEPENDENT,
        "detail": "Not connected in this runtime. The retrieval layer (real DB queries, permission "
                   "checks, action-proposal contract) is already separated from response generation, "
                   "so an LLM could be added as an additional response-formatting/understanding step "
                   "without changing how data is fetched or how actions are authorized - but this "
                   "requires provisioning and connecting an actual LLM API, which has not been done.",
    },
]


def get_capabilities_report() -> List[dict]:
    return [
        {"capability": c["capability"], "status": c["status"].value, "detail": c["detail"]}
        for c in AI_CAPABILITIES
    ]


UNTRUSTED_CONTENT_FIELDS = [
    "GenericDocument.description", "ClientDocument.description", "PaymentDocument.description",
    "ClientActivity.summary", "DailyTask.remarks", "DailyTask.delay_reason",
    "ProductionJob.remarks", "ProductionJob.blocker_reason", "Milestone.remarks",
]


def sanitize_untrusted_text(value: str, max_length: int = 500) -> str:
    """Applied to any of UNTRUSTED_CONTENT_FIELDS before it is echoed
    back in a chatbot response. Strips control/formatting characters
    that have no legitimate purpose in a short business note and could
    be used to disrupt how the text renders or, if a future LLM reads
    it as context, to attempt to inject fake delimiters - and caps
    length so no single field can dominate a response."""
    if not value:
        return value
    cleaned = "".join(ch for ch in value if ch.isprintable() or ch in ("\n", "\t"))
    cleaned = cleaned.strip()
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length].rstrip() + "..."
    return cleaned


# --- agents.py ---
"""Business AI Agents.

An "agent" here is a named, scoped view into the exact same
ChatService.process_message pipeline the chatbot itself uses - never a
separate implementation. This is a deliberate architectural choice:
process_message is where real authorization, real database grounding,
and the propose-then-confirm action contract already live and are
already tested. Routing every agent through it means an
agent inherits those guarantees automatically. A parallel
implementation would risk drifting out of sync with those guarantees
over time, and agents explicitly forbid "bypass permissions" and
"fabricate records" - the surest way to keep that promise is to not
build a second code path that could fail to uphold it.

What this module adds beyond the chatbot: named identity and honest
capability classification per business area, matching the exact
lifecycle agents follow (Observe permitted data -> Understand ->
Retrieve -> Reason -> Recommend -> Confirm if required -> Execute
authorized action -> Audit) - annotated below against what actually
happens in the current runtime.
"""

AGENT_DEFINITIONS = {
    "inventory": {
        "label": "Inventory Agent",
        "description": "Stock levels, low-stock/out-of-stock alerts, reorder shortfalls, material usage history.",
        "example_queries": ["what material low", "out of stock materials", "hdhmr usage summary", "what needs reordering"],
        "status": CapabilityStatus.IMPLEMENTED,
    },
    "sales": {
        "label": "Sales Agent",
        "description": "Client orders, sales history, estimate summaries, pending estimates, client/order counts.",
        "example_queries": ["patel ka order?", "shrangi sales history", "pending estimates", "how many clients"],
        "status": CapabilityStatus.IMPLEMENTED,
    },
    "project": {
        "label": "Project Agent",
        "description": "Order/project risk (blocked tasks, delivery proximity), delayed-project detection, next action per order.",
        "example_queries": ["what's blocking this order", "which projects are delayed", "what's next on mahek"],
        "status": CapabilityStatus.IMPLEMENTED,
    },
    "production": {
        "label": "Production Agent",
        "description": "Blocked and overdue production jobs, grouped by machine - real bottleneck identification.",
        "example_queries": ["production bottlenecks", "delayed production"],
        "status": CapabilityStatus.IMPLEMENTED,
    },
    "procurement": {
        "label": "Procurement Agent",
        "description": "Overdue deliveries, supplier purchase-history summaries, pending purchases.",
        "example_queries": ["delayed deliveries", "summarize supplier century plywood", "pending purchases"],
        "status": CapabilityStatus.IMPLEMENTED,
    },
    "finance_insight": {
        "label": "Finance Insight Agent",
        "description": "Outstanding payments, expense trend explanations, order profitability - master-only, matching the sensitivity of the underlying data.",
        "example_queries": ["show outstanding payments", "why did expenses increase", "what's our profit margin"],
        "status": CapabilityStatus.IMPLEMENTED,
    },
    "document": {
        "label": "Document Agent",
        "description": "Locates documents attached to an order after the same permission check the real document API applies. Never opens or reads file content.",
        "example_queries": ["find documents for sanket"],
        "status": CapabilityStatus.IMPLEMENTED,
    },
    "operations": {
        "label": "Operations Agent",
        "description": "Staff task lookups, leave queries, follow-ups due, staff summary.",
        "example_queries": ["pankaj's tasks", "shivani leave balance", "follow-ups due today", "staff summary"],
        "status": CapabilityStatus.IMPLEMENTED,
    },
}


CROSS_AGENT_LIMITATIONS = [
    {
        "capability": "Autonomous multi-step reasoning without user confirmation",
        "status": CapabilityStatus.NOT_VERIFIED,
        "detail": "No agent here decides on its own to chain several actions together. Each "
                   "response is one retrieval-and-answer turn; a mutation always stops at a "
                   "ProposedAction awaiting explicit user confirmation, never an autonomous "
                   "multi-step plan the agent executes by itself.",
    },
    {
        "capability": "Genuine LLM-based reasoning per agent",
        "status": CapabilityStatus.EXTERNAL_SERVICE_DEPENDENT,
        "detail": "Every agent's 'Reason' step is deterministic rule-based logic (thresholds, "
                   "date math, real sums) executed in Python, not an LLM inference. No external "
                   "LLM is connected in this runtime.",
    },
]


def get_agents_report() -> List[dict]:
    return [
        {
            "key": key, "label": a["label"], "description": a["description"],
            "example_queries": a["example_queries"], "status": a["status"].value,
        }
        for key, a in AGENT_DEFINITIONS.items()
    ] + [
        {"key": None, "label": "(applies to all agents)", "description": c["capability"],
         "example_queries": [], "status": c["status"].value, "detail": c["detail"]}
        for c in CROSS_AGENT_LIMITATIONS
    ]


def route_to_agent(
    agent_key: str, message: str, db: Session, user_role: str = "user",
    context: Optional[ChatContext] = None, current_employee_id: Optional[int] = None,
) -> Tuple[str, list, object, Optional[dict], list]:
    """Every agent's actual execution - deliberately identical to the
    chatbot's own entry point. agent_key is validated against the real
    agent list but otherwise carries no special privilege: it does not
    grant any capability process_message would not already grant the
    same user for the same message. This is what "agents cannot bypass
    permissions" means architecturally - there is no separate code
    path that could be made to skip a check the chatbot itself enforces."""
    if agent_key not in AGENT_DEFINITIONS:
        return (
            f"Unknown agent '{agent_key}'. Available: {', '.join(AGENT_DEFINITIONS.keys())}.",
            [], None, None, [],
        )
    # Deferred import: orchestration.py imports ChatContext/ProposedAction
    # from this file at its own module level, so a top-level import of
    # ChatService here would be a genuine circular import (whichever of
    # the two modules loads first fails with "cannot import name ...
    # from partially initialized module"). Deferring it to call time,
    # where it's actually needed, avoids the cycle entirely without
    # restructuring either module.
    from app.modules.ai.orchestration import ChatService
    return ChatService.process_message(
        message, db, user_role=user_role, context=context, current_employee_id=current_employee_id,
    )
