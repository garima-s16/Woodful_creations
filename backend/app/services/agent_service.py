"""Family 15 - Business AI Agents.

An "agent" here is a named, scoped view into the exact same
ChatService.process_message pipeline the chatbot itself uses - never a
separate implementation. This is a deliberate architectural choice:
process_message is where real authorization, real database grounding,
and the propose-then-confirm action contract already live and are
already tested (Family 14). Routing every agent through it means an
agent inherits those guarantees automatically. A parallel
implementation would risk drifting out of sync with those guarantees
over time, and Family 15 explicitly forbids "bypass permissions" and
"fabricate records" - the surest way to keep that promise is to not
build a second code path that could fail to uphold it.

What this module adds beyond the chatbot: named identity and honest
capability classification per business area, matching the exact
lifecycle Family 15 specifies (Observe permitted data -> Understand ->
Retrieve -> Reason -> Recommend -> Confirm if required -> Execute
authorized action -> Audit) - annotated below against what actually
happens in the current runtime.
"""
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session

from app.services.chat_service import ChatService
from app.schemas.chat import ChatContext
from app.services.ai_layer import CapabilityStatus

# Lifecycle stages, as implemented by routing through process_message:
#   Observe permitted data -> the incoming message + context (order_id,
#     client_id, etc.) the caller is already authorized to be viewing
#   Understand -> keyword/regex intent matching (deterministic, not LLM)
#   Retrieve -> real SQLAlchemy queries against actual records
#   Reason -> explicit rule-based logic (thresholds, date comparisons,
#     sums) - never an LLM inference
#   Recommend -> the assembled response text + suggestions
#   Confirm if required -> ProposedAction, never auto-executed
#   Execute authorized action -> only after the caller confirms, via
#     the same authorized endpoint the rest of the app uses
#   Audit -> the executed action (if any) is audit-logged by the real
#     endpoint it went through, exactly as a normal UI action would be

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

# Honest, agent-independent facts about what this runtime cannot do.
# Every agent inherits these limits identically, since they all route
# through the same pipeline.
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
    return ChatService.process_message(
        message, db, user_role=user_role, context=context, current_employee_id=current_employee_id,
    )
