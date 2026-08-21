"""Server-side status lifecycle rules for Estimates and Orders (Family
102). Centralized here for the same reason ID generation and client
matching are centralized (see id_generator.py, client_matching.py):
one place that defines what's legal, reused by every entry point
(REST API, and implicitly denied to the AI/chat layer, which never
calls these directly - see Family 102 section 16), so the rule can
never drift or be bypassed by adding a second code path.

A frontend dropdown listing "valid" options is not validation - it's
a convenience. The real rule lives here and is enforced in
app/api/routes/estimates.py / orders.py before any status write.
"""
from typing import Optional


# ---------------------------------------------------------------------
# Estimates
# ---------------------------------------------------------------------

# The existing codebase already used draft/sent/approved/rejected
# (Woodful's own vocabulary for the generic Draft/Sent/Accepted/
# Rejected states) - "expired" and "cancelled" are the two genuinely
# missing terminal states Family 102 requires, added here rather than
# replacing the existing three-state names with generic ones.
# "closed" is a further terminal state, system-set only: an approved
# estimate that has actually been converted into an Order. It is
# deliberately NOT reachable through validate_estimate_status_transition
# (see ESTIMATE_TRANSITIONS below) - a person can never PUT status
# directly to "closed"; only the order-conversion route sets it,
# atomically alongside claiming the estimate's order_id, so the two
# facts (order_id set, status closed) can never drift apart.
ESTIMATE_STATUSES = {"draft", "sent", "approved", "rejected", "expired", "cancelled", "closed"}

# Once an estimate reaches one of these, it's a finalized historical
# record (Family 102 section 4) - further changes to its content
# (line items, costs, discount, tax, valid_until) are blocked; a
# genuinely different quote is a new revision (see /revise), not an
# edit to a decided estimate.
ESTIMATE_FINALIZED_STATUSES = {"approved", "rejected", "expired", "cancelled", "closed"}

ESTIMATE_TRANSITIONS = {
    # A draft can be sent for formal review, or decided on directly
    # (e.g. a verbal agreement, or staff marking it approved/rejected
    # immediately) - both paths are real, established usage (see
    # tests/test_sales_estimate_conversion.py, which predates this
    # rule and exercises draft -> approved and draft -> rejected
    # directly). "sent" is a real intermediate state, not a mandatory
    # gate every estimate must pass through.
    "draft": {"sent", "approved", "rejected", "cancelled"},
    "sent": {"approved", "rejected", "expired", "cancelled"},
    # An approved estimate can still be cancelled (the client backed out
    # before an order was actually created) but never revert to
    # draft/sent - and once it's been converted to an order, the order
    # itself becomes the record of what happened; the caller is
    # expected to check order_id separately before allowing this.
    "approved": {"cancelled"},
    "rejected": set(),
    "expired": set(),
    "cancelled": set(),
    "closed": set(),
}


def validate_estimate_status_transition(current: str, new: str) -> Optional[str]:
    """Returns an error message if the transition is not allowed, or
    None if it's fine. Setting status to its own current value is
    always a no-op success (an update that doesn't touch other fields
    but happens to re-send the current status shouldn't be treated as
    an illegal transition)."""
    if new not in ESTIMATE_STATUSES:
        return f"'{new}' is not a valid estimate status. Valid values: {', '.join(sorted(ESTIMATE_STATUSES))}."
    if current == new:
        return None
    allowed = ESTIMATE_TRANSITIONS.get(current, set())
    if new not in allowed:
        return f"An estimate cannot move from '{current}' to '{new}'."
    return None


# ---------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------

# The existing codebase's project_status is a real, detailed production
# pipeline (Enquiry -> ... -> Completed) - richer and more specific to
# how Woodful actually runs a job than the generic "Draft/Confirmed/In
# Progress/Completed" list Family 102 suggests as a minimum, so it's
# kept as-is per "reuse the existing lifecycle if it's already correct".
# "Cancelled" was the one genuinely missing state (no way to void an
# order previously existed at all) and is added here.
ORDER_PROJECT_STATUSES = {
    "Enquiry", "Designing", "Approved", "Material Purchase", "Cutting", "Edge Banding",
    "Assembly", "Painting", "Ready for Dispatch", "Installation", "Completed", "On Hold", "Cancelled",
}

# design_status / execution_status / delivery_status share one simple
# three-state vocabulary already used consistently across all three
# fields in the existing frontend (SIMPLE_STATUS_OPTIONS).
ORDER_SUB_STATUSES = {"Pending", "In Progress", "Completed"}


def validate_order_status_value(field_name: str, value: str) -> Optional[str]:
    """Order status fields don't have a meaningful linear transition
    order the way an estimate's approval flow does (a job can move
    Cutting -> On Hold -> Cutting again if a hold is lifted, for
    example) - so unlike estimates, this only validates that the value
    is one of the real, known values for that field, not a specific
    from-to transition. "Cancelled" is always reachable from any
    project_status (a job can be called off at any stage)."""
    if field_name == "project_status":
        if value not in ORDER_PROJECT_STATUSES:
            return f"'{value}' is not a valid order stage. Valid values: {', '.join(sorted(ORDER_PROJECT_STATUSES))}."
        return None
    if field_name in ("design_status", "execution_status", "delivery_status"):
        if value not in ORDER_SUB_STATUSES:
            return f"'{value}' is not a valid {field_name.replace('_', ' ')}. Valid values: {', '.join(sorted(ORDER_SUB_STATUSES))}."
        return None
    return None
