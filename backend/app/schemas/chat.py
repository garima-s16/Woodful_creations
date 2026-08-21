import re
from pydantic import BaseModel
from typing import List, Optional

DEICTIC_REFERENCE_WORDS = [
    "usme", "usmein", "ismein", "iska", "iski", "iske", "uska", "uski", "uske",
    "it", "that", "this one", "about it", "in it",
]
_DEICTIC_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in DEICTIC_REFERENCE_WORDS) + r")\b"
)


def _has_deictic_reference(message: str) -> bool:
    return bool(_DEICTIC_PATTERN.search(message))


class CartItemContext(BaseModel):
    """One line of the client-side purchase cart, sent along so the
    assistant can answer questions about it - the cart itself has no
    backend representation at all (see cartSlice.js), so this is the
    only way the server ever finds out what's in it."""
    material_id: int
    quantity: float


class ChatContext(BaseModel):
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


class ChatRequest(BaseModel):
    message: str
    context: Optional[ChatContext] = None


class ProposedAction(BaseModel):
    """A structured, high-impact action the assistant has parsed from the
    conversation but has NOT executed. The frontend shows this for
    explicit user confirmation before calling the real endpoint - the
    assistant never modifies business data on its own. `action_type`
    tells the frontend which confirmation UI/endpoint to use; `payload`
    is the exact request body that endpoint expects."""
    action_type: str
    summary: str
    payload: dict


class ChatResponse(BaseModel):
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
