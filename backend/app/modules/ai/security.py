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
from enum import Enum
from typing import List


class CapabilityStatus(str, Enum):
    IMPLEMENTED = "IMPLEMENTED"
    EXTERNAL_SERVICE_DEPENDENT = "EXTERNAL-SERVICE DEPENDENT"
    MOCKED = "MOCKED"
    NOT_VERIFIED = "NOT VERIFIED"


# The honest inventory. Each entry names a real target capability from
# the brief and states plainly what the current runtime actually does -
# never implying LLM reasoning where there is deterministic keyword
# matching, and never implying a document-understanding capability
# that has no implementation to back it.
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
                   "(app/utils/purchase_import.py) - it is not part of the chatbot and does not "
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


# Fields across the app that hold user-supplied free text and are ever
# echoed back verbatim in a chatbot response (e.g. a document
# description, an activity summary). Not a prompt-injection risk today
# - the current chatbot is deterministic pattern matching, not an LLM
# that "reads" this text as instructions - but if a real LLM is ever
# connected per the architecture above, any text from this category
# must be passed as clearly-delimited DATA, never concatenated into an
# instruction/system prompt. Documented here so that boundary is not
# lost when this module is eventually the AI's actual view of them.
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
