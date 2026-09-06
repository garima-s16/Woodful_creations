"""Rule-based business-intelligence assistant - the first-pass matcher.
Answers common questions by querying the current domain directly via
keyword/pattern matching, not language understanding. When this
matching comes up empty, it falls through to a real Gemini integration
(see ai_gateway.py, invoked below) rather than returning a generic
"I don't understand" - so the "not a real LLM" description applies
only to this module's own first-pass logic, not the assistant as a
whole.

Context-awareness: when the frontend passes a ChatContext (the record
the user is currently viewing), "this order" / "this material" style
questions are answered against that specific record instead of falling
through to a generic aggregate answer.

Propose-confirm actions: the assistant never modifies business data on
its own. When it recognizes a request to record a payment, it parses
the details into a ProposedAction and returns it alongside the reply -
the frontend shows this for explicit confirmation, and only then calls
the real POST /api/payments/ endpoint (which has its own RBAC and
audit logging - this service never bypasses either).

Structured results: queries that answer "which records" (not just "how
many") return a `records` list alongside the text - each one tagged
with enough to render a clickable card and link straight to the real
detail page, rather than a wall of prose the user has to go find the
records from themselves.

This is the dispatch core only - process_message/_dispatch route each
message to the right domain handler, and _answer_from_context/
_check_learned_intent are tightly bound to that same dispatch sequence
(the frontend-provided-context fast path and the Gemini-fallback
short-circuit, respectively). Every domain's actual query/action
implementations live in their own module (chat_inventory.py,
chat_sales.py, chat_hr.py, chat_operations.py, chat_catalog.py) -
split out of what was previously one 2250-line, 55-method file mixing
every domain together under one ChatService class."""
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.modules.inventory.models import Material
from app.modules.procurement.models import Supplier
from app.modules.sales.models import Order
from app.modules.clients.models import Client
from app.modules.hr.models import Employee, Attendance
from app.modules.sales.order_service import OrderService
from app.modules.ai.schemas import ChatContext, ProposedAction

from app.modules.inventory.services import (
    _route_ambiguous_hindi_add, _route_material_action, _route_material_query,
    _out_of_stock, _pending_purchases, _replenishment_requirements, _summarize_supplier,
    _recent_purchases, _stock_summary, _low_stock, _material_usage_summary, _at_risk_orders,
)
from app.modules.sales.services import (
    _order_risk_workspace, _continue_payment, _propose_payment, _profitability_summary,
    _route_order_products, _route_sales_history_query, _payments_summary, _pending_estimates,
    _orders_summary, _route_client_order_query, _clients_summary, _route_estimate_summary,
)
from app.modules.hr.services import (
    _route_add_employee_action, _assign_task_action, _complete_task_action,
    _route_salary_query, _staff_summary, _route_task_query, _route_leave_query,
)
from app.modules.operations.services import (
    _whats_changed_this_month, _production_bottlenecks, _daily_briefing,
    _delayed_deliveries, _route_excel_via_chat, _follow_up_suggestions, _delayed_projects,
    _explain_expense_change, _route_next_action, _route_find_documents,
)
from app.modules.catalog.services import (
    _route_delete_product_action, _route_add_product_action, _optimize_cart,
    _route_product_search,
)

THIS_RECORD_WORDS = ["this order", "this material", "this client", "this employee", "this supplier",
                      "summarize", "summarise", "should i reorder", "reorder this", "compare this supplier",
                      # "this project" is how the budget suggestion refers to an order
                      # (matching the Woodful UI's own "project" terminology), and "budget" on its
                      # own covers the case where context is already set from viewing an order page.
                      "this project", "budget"]
PAYMENT_INTENT_WORDS = ["record a payment", "record payment", "log a payment", "log payment", "add a payment"]
COMPLETE_TASK_WORDS = ["mark this done", "mark this task done", "mark this task as done", "mark as done",
                        "complete this task", "this is done", "task complete", "ye done kar", "ye complete"]
ORDER_BLOCKING_WORDS = ["what is blocking", "what's blocking", "kya problem hai", "kya scene hai",
                         "why is this delayed", "is this order at risk", "is this at risk"]


class ChatService:
    @staticmethod
    def process_message(message: str, db: Session, user_role: str = "user",
                         context: Optional[ChatContext] = None, current_employee_id: Optional[int] = None,
                         request=None, auth: Optional[dict] = None,
                         ) -> Tuple[str, List[str], Optional[ProposedAction], Optional[dict], List[dict]]:
        m = message.lower()

        if any(w in m for w in COMPLETE_TASK_WORDS):
            text, suggestions, records = _complete_task_action(db, user_role, current_employee_id, context)
            return text, suggestions, None, None, records

        assign_result = _assign_task_action(m, db, context, user_role)
        if assign_result:
            text, suggestions, records = assign_result
            return text, suggestions, None, None, records

        if any(w in m for w in ORDER_BLOCKING_WORDS) and context:
            record_type, record_id = context.resolved_with_reference(m)
            if record_type == "order" and record_id:
                text, suggestions, records = _order_risk_workspace(db, record_id, user_role, message)
                return text, suggestions, None, None, records

        # Continuing a payment proposal started on a previous turn (the
        # frontend echoes back whatever `clarification` it was given).
        if context and context.pending and context.pending.get("type") == "record_payment":
            result = _continue_payment(m, user_role, context.pending, db)
            if result:
                return result

        if any(w in m for w in PAYMENT_INTENT_WORDS) and context and context.order_id:
            proposal = _propose_payment(m, db, user_role, context.order_id)
            if proposal:
                return proposal

        add_employee_action = _route_add_employee_action(m, db, user_role)
        if add_employee_action:
            return add_employee_action

        delete_product_action = _route_delete_product_action(m, db, user_role)
        if delete_product_action:
            return delete_product_action

        add_product_action = _route_add_product_action(m, db, user_role)
        if add_product_action:
            return add_product_action

        ambiguous_hindi_add = _route_ambiguous_hindi_add(m, db)
        if ambiguous_hindi_add:
            return ambiguous_hindi_add

        material_action = _route_material_action(m, db, user_role)
        if material_action:
            return material_action

        if context and context.cart_items and any(w in m for w in ["optimize", "cheapest supplier", "best supplier"]):
            if user_role in ("master",):
                text, suggestions, records = _optimize_cart(db, context.cart_items)
                return text, suggestions, None, None, records
            return "Supplier price comparison is available to master accounts only.", [], None, None, []

        text, suggestions, records = ChatService._dispatch(m, db, user_role, context, current_employee_id)

        # Gemini only gets a turn when the existing
        # deterministic parsing found genuinely nothing.
        # Every already-working command is completely untouched by
        # this - it never even reaches here for those.
        if text == "I didn't quite catch that. Try asking about stock, orders, clients, payments, or staff.":
            learned = ChatService._check_learned_intent(m, db, user_role)
            if learned:
                learned_text, learned_records = learned
                return learned_text, [], None, None, learned_records

            from app.modules.ai import gateway as ai_gateway
            conversation_context = ai_gateway.build_conversation_context(context)
            gemini_result = ai_gateway.handle_message(
                message, db, user_role, conversation_context,
                request=request, auth=auth, current_employee_id=current_employee_id,
            )
            if gemini_result:
                gemini_text, gemini_suggestions, gemini_proposal, gemini_records = gemini_result
                return gemini_text, gemini_suggestions, gemini_proposal, None, gemini_records

        return text, suggestions, None, None, records

    @staticmethod
    def _check_learned_intent(m: str, db: Session, user_role: str):
        """The deterministic parser
        consulting an approved learning candidate BEFORE falling back
        to Gemini, so a phrase Woodful has already learned no longer
        needs a Gemini call at all - Gemini usage should decrease
        over time as more phrases are learned and approved.

        Deliberately scoped to only the two read tools that take zero
        arguments (get_upcoming_holidays, get_low_stock_materials -
        confirmed directly against ai_gateway.py's own tool schemas,
        not assumed). A ChatLearningCandidate only ever stores a tool
        name, never the arguments Gemini originally extracted (Section
        24's conservative data policy), so there is no safe way to
        recover what a parameterized tool like get_material_stock
        would need (which material) from the stored candidate alone -
        attempting that would risk calling the tool with an empty or
        wrong argument. Widening this beyond no-argument tools would
        need storing/deriving arguments safely first, which this
        implementation does not attempt.

        A plain database lookup only - approving a candidate never
        generates or executes any code."""
        from app.modules.ai.models import ChatLearningCandidate
        from app.modules.ai import gateway as ai_gateway

        normalized = m.strip()
        if not normalized:
            return None

        candidate = db.query(ChatLearningCandidate).filter(
            ChatLearningCandidate.normalized_phrase == normalized,
            ChatLearningCandidate.status == "approved",
            ChatLearningCandidate.resolved_tool.in_(["get_upcoming_holidays", "get_low_stock_materials"]),
        ).first()
        if not candidate:
            return None

        tool_fn = ai_gateway.READ_TOOL_DISPATCH.get(candidate.resolved_tool)
        if not tool_fn:
            return None
        outcome = tool_fn(db, {}, user_role)
        if isinstance(outcome, tuple):
            return outcome
        return outcome, []

    @staticmethod
    def _dispatch(m: str, db: Session, user_role: str, context: Optional[ChatContext],
                  current_employee_id: Optional[int] = None) -> Tuple[str, List[str], List[dict]]:
        if context and any(w in m for w in THIS_RECORD_WORDS):
            contextual = ChatService._answer_from_context(m, db, user_role, context)
            if contextual:
                text, suggestions = contextual
                return text, suggestions, []

        task_result = _route_task_query(m, db, current_employee_id)
        if task_result:
            return task_result

        leave_result = _route_leave_query(m, db, current_employee_id, user_role)
        if leave_result:
            return leave_result

        salary_result = _route_salary_query(m)
        if salary_result:
            return salary_result

        mentions_orders = any(w in m for w in ["order", "orders"])
        mentions_risk = any(w in m for w in ["at risk", "blocked", "delayed", "material blocking"])
        if mentions_orders and mentions_risk:
            return _at_risk_orders(db)
        if any(w in m for w in ["needs reordering", "replenishment", "to replenish"]):
            return _replenishment_requirements(db, user_role)
        if any(w in m for w in ["low stock", "reorder", "alert", "kam hai", "kam h", "material low", "materials low", "materials are low"]):
            return _low_stock(db, user_role)
        if "out of stock" in m or "out-of-stock" in m:
            return _out_of_stock(db, user_role)
        if any(w in m for w in ["purchased recently", "recent purchase", "bought recently"]):
            if user_role in ("master",):
                return _recent_purchases(db)
            return "Purchase information is available to master accounts only.", [], []
        if any(w in m for w in ["inventory value", "stock value", "purchase cost", "how much did we spend", "spent on"]):
            if user_role in ("master",):
                return _stock_summary(db, user_role)
            return "You don't have access to view this data.", [], []
        excel_query = _route_excel_via_chat(m, db, user_role)
        if excel_query:
            return excel_query
        client_order_query = _route_client_order_query(m, db, user_role, context)
        if client_order_query:
            return client_order_query
        sales_history_query = _route_sales_history_query(m, db, user_role)
        if sales_history_query:
            return sales_history_query
        estimate_summary = _route_estimate_summary(m, db, user_role, context)
        if estimate_summary:
            return estimate_summary
        order_products = _route_order_products(m, db, user_role, context)
        if order_products:
            return order_products
        product_search = _route_product_search(m, db, user_role)
        if product_search:
            return product_search
        next_action = _route_next_action(m, db, context)
        if next_action:
            return next_action
        if any(w in m for w in ["bottleneck", "production delay", "delayed production"]):
            return _production_bottlenecks(db)
        if any(w in m for w in ["delayed project", "delayed projects", "which projects are delayed", "projects are behind", "project late", "projects late", "late project"]):
            return _delayed_projects(db)
        if any(w in m for w in ["why did expenses", "why are expenses", "expenses increase", "expenses went up", "expenses go up"]):
            return _explain_expense_change(db, user_role)
        if any(w in m for w in ["what changed this month", "what changed", "changed this month"]):
            return _whats_changed_this_month(db, user_role)
        find_documents = _route_find_documents(m, db, user_role)
        if find_documents:
            return find_documents
        if (any(w in m for w in ["follow-up", "follow up", "followup"]) and any(w in m for w in ["due", "pending", "today"])) \
                or any(w in m for w in ["followed up", "who needs follow"]):
            if user_role in ("master",):
                return _follow_up_suggestions(db)
            return "Follow-up information is available to master accounts only.", [], []
        if any(w in m for w in ["delayed delivery", "delayed deliveries", "overdue delivery", "overdue deliveries"]):
            if user_role in ("master",):
                return _delayed_deliveries(db)
            return "Delivery information is available to master accounts only.", [], []
        supplier_summary = _summarize_supplier(m, db, user_role)
        if supplier_summary:
            return supplier_summary
        if any(w in m for w in ["needs attention", "what needs attention", "anything urgent", "daily briefing", "morning briefing"]):
            return _daily_briefing(db, user_role)
        if "usage" in m:
            usage_summary = _material_usage_summary(m, db)
            if usage_summary:
                return usage_summary
        material_query = _route_material_query(m, db)
        if material_query:
            return material_query
        if any(w in m for w in ["stock", "material", "inventory"]):
            return _stock_summary(db, user_role)
        if any(w in m for w in ["order", "project", "pipeline"]):
            return _orders_summary(db)
        if any(w in m for w in ["client", "customer", "find a client"]):
            return _clients_summary(db)
        if any(w in m for w in ["payment", "revenue", "pending amount", "balance", "owe"]):
            if user_role in ("master",):
                return _payments_summary(db)
            return "Financial information is available to master accounts only.", [], []
        if any(w in m for w in ["profit", "margin", "profitability"]):
            if user_role in ("master",):
                return _profitability_summary(db)
            return "Profit and margin information is available to master accounts only.", [], []
        if any(w in m for w in ["my attendance"]):
            if current_employee_id is None:
                return ("Your account isn't linked to an employee record, so I can't look up "
                        "your attendance."), [], []
            records = db.query(Attendance).filter(Attendance.employee_id == current_employee_id).order_by(
                Attendance.date.desc()
            ).limit(10).all()
            if not records:
                return "You have no attendance records yet.", [], []
            items = [{
                "type": "Attendance", "label": a.date.strftime("%d %b %Y"),
                "sublabel": a.attendance_status, "path": "/attendance",
            } for a in records]
            return f"Your last {len(records)} attendance record(s):", [], items
        if any(w in m for w in ["employee", "staff", "attendance"]):
            return _staff_summary(db)
        if any(w in m for w in ["pending purchase", "purchases pending"]):
            if user_role in ("master",):
                return _pending_purchases(db)
            return "Purchase information is available to master accounts only.", [], []
        if any(w in m for w in ["pending estimate", "estimates pending", "estimates awaiting", "follow up on estimate", "follow-up on estimate"]):
            if user_role in ("master",):
                return _pending_estimates(db)
            return "Estimate information is available to master accounts only.", [], []
        if "help" in m:
            return (
                "I can answer questions about stock/materials, orders, clients, payments "
                "(master only), and staff. Try asking about low stock, orders at risk, "
                "pending orders, or client count.",
                ["Check low stock", "Orders at risk", "Show pending orders"], [],
            )
        return (
            "I didn't quite catch that. Try asking about stock, orders, clients, payments, or staff.",
            ["Check low stock", "Show pending orders", "Show staff summary"], [],
        )

    @staticmethod
    def _answer_from_context(m: str, db: Session, user_role: str, context: ChatContext):
        record_type, record_id = context.resolved_with_reference(m)
        if not record_type:
            return None

        if record_type == "order":
            order = db.query(Order).filter(Order.id == record_id).first()
            if not order:
                return None
            client_name = order.client.name if order.client else "Unknown client"
            if "budget" in m:
                # Answers the "Why is this project running at a loss?" /
                # "How is this project's profitability tracking?" suggestion.
                # Woodful has no genuine planned/project-budget field - order_value
                # is the order's price, not a declared cost ceiling - so this never
                # claims a project is "over budget" (negative profit isn't the same
                # thing as exceeding a planned budget that doesn't exist here).
                # Reuses OrderService.profitability() (the exact same figures the
                # order detail page's own profitability panel already shows) rather
                # than a second, independently-derived calculation - and stays
                # behind the same master-only restriction that endpoint already
                # enforces, so a "user"-role viewer sees no financial figures here
                # either.
                if user_role not in ("master",):
                    return "Profitability details for this project aren't available to your account role.", []
                figures = OrderService.profitability(db, order)
                running_at_a_loss = figures["estimated_gross_profit"] < 0
                lines = [
                    f"{order.order_code}: order value Rs {figures['order_value']:,.2f}, "
                    f"actual direct costs so far Rs {figures['actual_direct_costs']:,.2f} "
                    f"(Rs {figures['material_cost']:,.2f} material + Rs {figures['project_expenses']:,.2f} expenses).",
                ]
                if running_at_a_loss:
                    lines.append(f"Costs so far exceed the order value by Rs {abs(figures['estimated_gross_profit']):,.2f}.")
                else:
                    lines.append(
                        f"Estimated gross profit so far: Rs {figures['estimated_gross_profit']:,.2f} "
                        f"({figures['gross_margin_ratio'] * 100:.1f}% margin)."
                    )
                return " ".join(lines), []
            lines = [
                f"{order.order_code} for {client_name} - {order.project_type or 'project'}.",
                f"Stage: {order.project_status}. Progress: {order.progress_percent}%.",
                f"Order value: Rs {float(order.order_value):,.2f}.",
            ]
            if user_role in ("master",):
                lines.append(f"Received: Rs {float(order.total_received):,.2f}. Outstanding: Rs {float(order.balance):,.2f}.")
            if order.delivery_date:
                lines.append(f"Delivery date: {order.delivery_date.strftime('%d %b %Y')}.")
            return " ".join(lines), ["Record Payment", "Show order pipeline"]

        if record_type == "supplier":
            supplier = db.query(Supplier).filter(Supplier.id == record_id).first()
            if not supplier:
                return None
            lines = [f"{supplier.name} ({supplier.supplier_code}): {len(supplier.purchases)} purchases on record."]
            if supplier.purchases and user_role in ("master",):
                total_spend = sum((float(p.invoice_total or 0) for p in supplier.purchases), 0.0)
                lines.append(f"Total spend: Rs {total_spend:,.2f}.")
            material_names = [sm.material.name for sm in supplier.supplier_materials if sm.material]
            if material_names:
                lines.append(f"Supplies: {', '.join(material_names[:5])}" + (" and more." if len(material_names) > 5 else "."))
            return " ".join(lines), []

        if record_type == "material":
            material = db.query(Material).filter(Material.id == record_id).first()
            if not material:
                return None
            if "reorder" in m:
                if material.current_stock <= material.minimum_stock:
                    shortfall = material.minimum_stock - material.current_stock
                    return (
                        f"Yes - {material.name} is at {material.current_stock} {material.unit}, "
                        f"at or below the reorder level of {material.minimum_stock} {material.unit}. "
                        f"Consider ordering at least {shortfall} {material.unit}.",
                        [],
                    )
                return (
                    f"Not yet - {material.name} has {material.current_stock} {material.unit} available, "
                    f"above the reorder level of {material.minimum_stock} {material.unit}.",
                    [],
                )
            return (
                f"{material.name} ({material.material_code}): {material.current_stock} {material.unit} available, "
                f"reorder level {material.minimum_stock} {material.unit}, status {material.stock_status}.",
                ["Should I reorder this?"],
            )

        if record_type == "client":
            client = db.query(Client).filter(Client.id == record_id).first()
            if not client:
                return None
            lines = [f"{client.name} ({client.client_code}): {len(client.orders)} orders."]
            if user_role in ("master",):
                total_sales = sum((o.order_value for o in client.orders), 0)
                lines.append(f"Rs {float(total_sales):,.2f} in total order value.")
            return " ".join(lines), []

        if record_type == "employee":
            employee = db.query(Employee).filter(Employee.id == record_id).first()
            if not employee:
                return None
            return (
                f"{employee.name} ({employee.employee_code}), {employee.department or 'no department'}. Status: {employee.status}.",
                [f"Show {employee.name.split()[0]}'s tasks"],
            )

        return None

