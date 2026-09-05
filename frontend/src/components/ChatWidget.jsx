import React, { useState, useRef, useEffect } from 'react';
import { motion } from 'motion/react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useSelector, useDispatch } from 'react-redux';
import { chatAPI, paymentsAPI, materialsAPI, employeesAPI, reportsAPI, ordersAPI, productsAPI, estimatesAPI, dailyTasksAPI, issuesAPI, stockAPI, purchasesAPI, leavesAPI } from '../utils/api';
import AssistantMascot from './AssistantMascot';
import SendEmailModal from './common/SendEmailModal';
import { clearPendingMessage } from '../redux/slices/chatUiSlice';
import { addToCart } from '../redux/slices/cartSlice';
import '../styles/components/ChatWidget.css';

function contextualGreetingSuggestion(params, pathname, cartOpen) {
  // Checked first - the cart drawer can be open on top of any page, so
  // this isn't mutually exclusive with a route param the way the
  // record-based ones below are.
  if (cartOpen) return 'Optimize this purchase';
  if (params.orderId) return 'Summarize this order';
  if (params.materialId) return 'Tell me about this material';
  if (params.clientId) return 'Summarize this client';
  if (params.employeeId) return 'Summarize this employee';
  if (params.supplierId) return 'Compare this supplier';
  // Page-level context (no specific record id) - the materials catalog
  // list itself, not a single material's detail page.
  if (pathname === '/materials') return 'What should I reorder?';
  return null;
}

// Budget-aware suggestion for a project (order) page, layered
// on top of contextualGreetingSuggestion above rather than replacing it
// (that function's existing behavior - e.g. "Summarize this order" -
// is left untouched). budgetSuggestion is only ever a value the caller
// already resolved from the real backend profitability figure (or null
// while it's loading / unavailable) - this function never decides
// over-budget itself, it only decides whether/where to slot the
// already-decided suggestion in.
function buildContextualSuggestions(params, pathname, cartOpen, budgetSuggestion) {
  const primary = contextualGreetingSuggestion(params, pathname, cartOpen);
  const extras = params.orderId && budgetSuggestion ? [budgetSuggestion] : [];
  return [primary, ...extras].filter(Boolean);
}

function ChatWidget() {
  const params = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const cartOpen = useSelector((state) => state.cart.isOpen);
  const cartItems = useSelector((state) => state.cart.items);
  const pendingCommand = useSelector((state) => state.chatUi.pendingMessage);
  const [open, setOpen] = useState(false);
  // Resolved from the EXISTING master-only profitability
  // endpoint (same one the order detail page's own profitability panel
  // already calls), never recomputed here. null means "not known yet /
  // not applicable" (still loading, no order in context, or a non-master
  // viewer the endpoint itself returned 403 for) - in every one of those
  // cases buildContextualSuggestions above simply omits the budget
  // suggestion rather than guessing.
  const [budgetSuggestion, setBudgetSuggestion] = useState(null);
  const [messages, setMessages] = useState(() => {
    const base = ['Check Low Stock', 'Show Outstanding Payments', 'Show Active Orders', "Today's Tasks"];
    const contextual = buildContextualSuggestions(params, location.pathname, cartOpen, null);
    return [{
      role: 'assistant',
      text: 'Hi, I\'m the Woodful Assistant. Ask me about stock, orders, clients, payments, or staff.',
      suggestions: [...contextual, ...base],
    }];
  });
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [emailReview, setEmailReview] = useState(null); // { messageIndex, actionType, payload } | null
  const [completedSteps, setCompletedSteps] = useState(0);
  const LOADING_STEPS = ['Understanding request', 'Checking permissions', 'Fetching from Woodful'];
  useEffect(() => {
    if (!loading) { setCompletedSteps(0); return undefined; }
    const interval = setInterval(
      () => setCompletedSteps((s) => Math.min(s + 1, LOADING_STEPS.length - 1)),
      450,
    );
    return () => clearInterval(interval);
  }, [loading]);

  // Woodful's data model has no genuine planned/project-budget field -
  // order_value is the order's price, not a declared cost ceiling, so
  // "over budget" is not something the figures below can actually
  // support (a project can be profitable and still have cost more than
  // planned, or vice versa - see OrderService.profitability). This uses
  // the same OrderService.profitability() figures the order detail
  // page's own profitability panel displays - never a second/independent
  // calculation, and never a hardcoded order id or boolean - but only
  // ever phrases the suggestion in terms of profitability, never
  // "budget", so the UI never claims something the data can't back up.
  // A 403 (a "user"-role viewer, per the existing master-only permission
  // on this endpoint) or any other failure just clears the suggestion -
  // the financial detail behind it stays exactly as restricted as it
  // already was on the order detail page.
  useEffect(() => {
    if (!params.orderId) {
      setBudgetSuggestion(null);
      return undefined;
    }
    let cancelled = false;
    ordersAPI.profitability(params.orderId).then((res) => {
      if (cancelled) return;
      const runningAtALoss = Number(res.data?.estimated_gross_profit) < 0;
      setBudgetSuggestion(runningAtALoss
        ? 'Why is this project running at a loss?'
        : "How is this project's profitability tracking?");
    }).catch(() => {
      if (!cancelled) setBudgetSuggestion(null);
    });
    return () => { cancelled = true; };
  }, [params.orderId]);

  // The initial greeting's contextual suggestions were only ever computed
  // once at mount (useState's lazy initializer never re-runs) - it never
  // reflected the page the user navigated to afterward, nor a budget
  // suggestion that resolves asynchronously after the page loads. This
  // refreshes it on every navigation and whenever the budget suggestion
  // above resolves, but only while the chat is still untouched (just the
  // greeting, no real conversation yet) - never rewrites an actual
  // conversation the user has already had.
  useEffect(() => {
    setMessages((prev) => {
      if (prev.length !== 1 || prev[0].role !== 'assistant') return prev;
      const base = ['Check Low Stock', 'Show Outstanding Payments', 'Show Active Orders', "Today's Tasks"];
      const contextual = buildContextualSuggestions(params, location.pathname, cartOpen, budgetSuggestion);
      return [{ ...prev[0], suggestions: [...contextual, ...base] }];
    });
  }, [location.pathname, params, cartOpen, budgetSuggestion]);
  const [pending, setPending] = useState(null);
  const [lastEntity, setLastEntity] = useState(null);
  const [lastExchange, setLastExchange] = useState(null); // { user, assistant } - for conversational context
  const endRef = useRef(null);

  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, open]);

  useEffect(() => {
    if (pendingCommand) {
      setOpen(true);
      send(pendingCommand);
      dispatch(clearPendingMessage());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pendingCommand]);

  const send = async (text) => {
    const message = (text ?? input).trim();
    if (!message) return;
    setMessages((prev) => [...prev, { role: 'user', text: message }]);
    setInput('');
    setLoading(true);

    // One param -> record_type mapping, not one context field per page.
    // Adding a new contextual page type (e.g. a future Purchase Cart
    // page) means adding one line here, not a new field on ChatContext.
    const PARAM_TO_RECORD_TYPE = [
      ['orderId', 'order'], ['clientId', 'client'], ['materialId', 'material'],
      ['employeeId', 'employee'], ['supplierId', 'supplier'], ['taskId', 'task'],
      ['estimateId', 'estimate'],
    ];
    const activeParam = PARAM_TO_RECORD_TYPE.find(([param]) => params[param]);
    const context = {
      record_type: activeParam ? activeParam[1] : undefined,
      record_id: activeParam ? Number(params[activeParam[0]]) : undefined,
      pending: pending || undefined,
      last_entity: lastEntity || undefined,
      last_user_message: lastExchange?.user || undefined,
      last_assistant_message: lastExchange?.assistant || undefined,
      cart_items: (cartOpen && cartItems.length > 0)
        ? cartItems.map((i) => ({ material_id: i.materialId, quantity: i.quantity }))
        : undefined,
    };
    const hasContext = Object.values(context).some((v) => v !== undefined);

    try {
      const res = await chatAPI.send(message, hasContext ? context : undefined);
      setPending(res.data.clarification || null);
      setLastEntity(res.data.last_entity || null);
      setLastExchange({ user: message, assistant: res.data.response });
      setMessages((prev) => [...prev, {
        role: 'assistant', text: res.data.response, suggestions: res.data.suggestions,
        proposedAction: res.data.proposed_action || null, records: res.data.records || [],
      }]);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setMessages((prev) => [...prev, { role: 'assistant', text: detail || 'Unable to answer that right now. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  // The assistant only ever prepares this - the real mutation happens
  // here, at the moment the user explicitly clicks Confirm, via the
  // same authenticated/RBAC'd/audited endpoint the relevant page itself
  // uses. One executor per action_type, not a special case handled
  // elsewhere - adding a new proposable action means adding one entry
  // here, not another `if` chain.
  const ACTION_EXECUTORS = {
    record_payment: { execute: (payload) => paymentsAPI.create(payload), successText: 'recorded.' },
    create_material: { execute: (payload) => materialsAPI.create(payload), successText: 'added to Material Master.' },
    create_employee: { execute: (payload) => employeesAPI.create(payload), successText: 'added as an employee.' },
    create_leave: { execute: (payload) => leavesAPI.create(payload), successText: 'recorded in the Leave Tracker.' },
    create_product: { execute: (payload) => productsAPI.create(payload), successText: 'added to Product Master.' },
    delete_product: { execute: (payload) => productsAPI.remove(payload.productId), successText: 'deleted.' },
    issue_stock: { execute: (payload) => issuesAPI.create(payload), successText: 'issued from stock.' },
    transfer_stock: { execute: (payload) => stockAPI.transfer(payload), successText: 'transferred.' },
    adjust_stock: { execute: (payload) => stockAPI.adjust(payload), successText: 'adjusted.' },
    receive_purchase: { execute: (payload) => purchasesAPI.receive(payload.purchaseId), successText: 'marked as received.' },
    add_to_cart: {
      execute: (payload) => dispatch(addToCart(payload)).unwrap(),
      successText: 'added to your cart.',
    },
    send_task_email: {
      execute: (payload) => dailyTasksAPI.sendEmail(payload.task_id),
      successText: 'emailed to the employee.',
    },
    create_daily_task: {
      execute: (payload) => dailyTasksAPI.create(payload),
      successText: 'assigned.',
    },
    update_daily_task: {
      execute: (payload) => {
        const { task_id, ...updateData } = payload;
        return dailyTasksAPI.update(task_id, updateData);
      },
      successText: 'updated.',
    },
  };

  const EMAIL_REVIEW_TYPES = new Set(['send_estimate_email', 'send_order_email', 'send_invoice_email', 'send_payment_receipt_email']);

  const confirmAction = async (messageIndex, action) => {
    if (EMAIL_REVIEW_TYPES.has(action.action_type)) {
      // Open the real review UI instead of sending immediately - the
      // proposal itself is left in place (not dismissed) until the
      // modal is closed or the email is actually sent, so "Confirm"
      // here means "let me review this," not "send it now."
      setEmailReview({ messageIndex, actionType: action.action_type, payload: action.payload });
      return;
    }
    setLoading(true);
    try {
      const executor = ACTION_EXECUTORS[action.action_type];
      if (!executor) throw new Error('Unsupported action type');
      await executor.execute(action.payload);
      setMessages((prev) => prev.map((msg, i) => (
        i === messageIndex
          ? { ...msg, proposedAction: null, resultText: executor.successText }
          : msg
      )));
    } catch (err) {
      const detail = err.response?.data?.detail;
      setMessages((prev) => [...prev, { role: 'assistant', text: detail || 'That action failed. Please try again or use the page directly.' }]);
    } finally {
      setLoading(false);
    }
  };

  // Maps each email-review action type to its real preview/send API
  // calls, given the payload the backend already resolved (a real
  // estimate_id/order_id/payment_id, never trusted client-side).
  const EMAIL_REVIEW_CONFIG = {
    send_estimate_email: {
      previewFn: (payload) => estimatesAPI.emailPreview(payload.estimate_id),
      sendFn: (payload, data) => estimatesAPI.sendEmail(payload.estimate_id, data),
    },
    send_order_email: {
      previewFn: (payload) => ordersAPI.emailPreview(payload.order_id, 'order'),
      sendFn: (payload, data) => ordersAPI.sendEmail(payload.order_id, 'order', data),
    },
    send_invoice_email: {
      previewFn: (payload) => ordersAPI.emailPreview(payload.order_id, 'invoice'),
      sendFn: (payload, data) => ordersAPI.sendEmail(payload.order_id, 'invoice', data),
    },
    send_payment_receipt_email: {
      previewFn: (payload) => paymentsAPI.emailPreview(payload.payment_id),
      sendFn: (payload, data) => paymentsAPI.sendEmail(payload.payment_id, data),
    },
  };

  const handleEmailReviewSent = () => {
    if (emailReview) {
      setMessages((prev) => prev.map((msg, i) => (
        i === emailReview.messageIndex
          ? { ...msg, proposedAction: null, text: `${msg.text}\n\nDone - emailed to the client.` }
          : msg
      )));
    }
    setEmailReview(null);
  };

  const dismissAction = (messageIndex) => {
    setMessages((prev) => prev.map((msg, i) => (
      i === messageIndex ? { ...msg, proposedAction: null, text: `${msg.text}\n\nOkay, not recorded.` } : msg
    )));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    send();
  };

  return (
    <div className="chat-widget">
      {open && (
        <div className="chat-panel">
          <div className="chat-panel-header">
            <AssistantMascot size={32} />
            <div className="chat-panel-title">
              <span className="chat-panel-name">Woodful Assistant</span>
              <span className="chat-panel-subtitle">Business Operations Assistant</span>
            </div>
            <button className="chat-panel-close" onClick={() => setOpen(false)} aria-label="Close">&times;</button>
          </div>
          <div className="chat-panel-body">
            {messages.map((m, i) => (
              <div key={i} className={`chat-row chat-row-${m.role}`}>
                {m.role === 'assistant' && <AssistantMascot size={26} />}
                <div className={`chat-bubble chat-${m.role}`}>
                  <div className="chat-text">{m.text}</div>
                  {m.resultText && (
                    <div className="chat-action-result">
                      <span className="chat-action-result-mark">&#10003;</span>
                      <span>{m.resultText}</span>
                    </div>
                  )}
                  {m.proposedAction && (
                    <div className="chat-proposed-action">
                      <div className="chat-proposed-summary">{m.proposedAction.summary}</div>
                      <div className="chat-proposed-buttons">
                        <button className="btn-primary" onClick={() => confirmAction(i, m.proposedAction)} disabled={loading}>Confirm</button>
                        <button className="btn-secondary" onClick={() => dismissAction(i)} disabled={loading}>Not now</button>
                      </div>
                    </div>
                  )}
                  {m.records?.length > 0 && (
                    <div className="chat-records">
                      {m.records.map((r, ri) => (
                        <motion.div
                          key={ri} className="chat-record-card"
                          initial={{ opacity: 0, y: 6 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.18, delay: ri * 0.04 }}
                          onClick={r.actions ? undefined : () => navigate(r.path)}
                          role={r.actions ? undefined : 'button'}
                          tabIndex={r.actions ? undefined : 0}
                          onKeyDown={r.actions ? undefined : (e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault();
                              navigate(r.path);
                            }
                          }}
                          style={r.actions ? {} : { cursor: 'pointer' }}
                        >
                          <span className="chat-record-type">{r.type}</span>
                          <span className="chat-record-label">{r.label}</span>
                          {r.sublabel && <span className="chat-record-sublabel">{r.sublabel}</span>}
                          {r.actions && (
                            <div className="chat-record-actions">
                              {r.actions.map((a, ai) => (
                                <button
                                  key={ai} className="chat-record-action-btn"
                                  onClick={() => (a.download_path
                                    ? window.open(reportsAPI.downloadUrl(a.download_path), '_blank')
                                    : navigate(a.path))}
                                >
                                  {a.label}
                                </button>
                              ))}
                            </div>
                          )}
                        </motion.div>
                      ))}
                    </div>
                  )}
                  {m.suggestions?.length > 0 && (
                    <div className="chat-suggestions">
                      {m.suggestions.map((s) => (
                        <button key={s} className="chat-suggestion" onClick={() => send(s)}>{s}</button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="chat-row chat-row-assistant">
                <AssistantMascot size={26} />
                <div className="chat-bubble chat-assistant chat-loading-bubble">
                  <div className="chat-loading-checklist">
                    {LOADING_STEPS.map((step, i) => (
                      <motion.div
                        key={step}
                        className={`chat-loading-step ${i < completedSteps ? 'done' : i === completedSteps ? 'active' : 'pending'}`}
                        initial={{ opacity: 0, x: -4 }}
                        animate={{ opacity: i <= completedSteps ? 1 : 0.4, x: 0 }}
                        transition={{ duration: 0.15 }}
                      >
                        <span className="chat-loading-step-mark">{i < completedSteps ? '✓' : '●'}</span>
                        <span>{step}</span>
                      </motion.div>
                    ))}
                  </div>
                </div>
              </div>
            )}
            <div ref={endRef} />
          </div>
          <form className="chat-panel-input" onSubmit={handleSubmit}>
            <input
              type="text" value={input} onChange={(e) => setInput(e.target.value)}
              placeholder="Ask Woodful Assistant..." disabled={loading}
            />
            <button type="submit" disabled={loading} aria-label="Send">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14M13 6l6 6-6 6" />
              </svg>
            </button>
          </form>
        </div>
      )}
      <SendEmailModal
        isOpen={!!emailReview}
        title="Review Email"
        previewFn={() => EMAIL_REVIEW_CONFIG[emailReview.actionType].previewFn(emailReview.payload)}
        sendFn={(data) => EMAIL_REVIEW_CONFIG[emailReview.actionType].sendFn(emailReview.payload, data)}
        onClose={() => setEmailReview(null)}
        onSent={handleEmailReviewSent}
      />
      <button className="chat-fab" onClick={() => setOpen((v) => !v)} aria-label="Open Woodful Assistant">
        {open ? (
          <span className="chat-fab-close">&times;</span>
        ) : (
          <>
            <AssistantMascot size={36} />
            <span className="chat-fab-label">Woodful Assistant</span>
          </>
        )}
      </button>
    </div>
  );
}

export default ChatWidget;
