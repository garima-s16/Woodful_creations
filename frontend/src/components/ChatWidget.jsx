import React, { useState, useRef, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { chatAPI, paymentsAPI } from '../utils/api';
import AssistantMascot from './AssistantMascot';
import '../styles/components/ChatWidget.css';

function contextualGreetingSuggestion(params) {
  if (params.orderId) return 'Summarize this order';
  if (params.materialId) return 'Should I reorder this?';
  if (params.clientId) return 'Summarize this client';
  if (params.employeeId) return 'Summarize this employee';
  return null;
}

function ChatWidget() {
  const params = useParams();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState(() => {
    const base = ['Check Low Stock', 'Show Outstanding Payments', 'Show Active Orders', "Today's Tasks"];
    const contextual = contextualGreetingSuggestion(params);
    return [{
      role: 'assistant',
      text: 'Hi, I\'m the Woodful Assistant. Ask me about stock, orders, clients, payments, or staff.',
      suggestions: contextual ? [contextual, ...base] : base,
    }];
  });
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    if (open) endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, open]);

  const send = async (text) => {
    const message = (text ?? input).trim();
    if (!message) return;
    setMessages((prev) => [...prev, { role: 'user', text: message }]);
    setInput('');
    setLoading(true);

    const context = {
      order_id: params.orderId ? Number(params.orderId) : undefined,
      client_id: params.clientId ? Number(params.clientId) : undefined,
      material_id: params.materialId ? Number(params.materialId) : undefined,
      employee_id: params.employeeId ? Number(params.employeeId) : undefined,
    };
    const hasContext = Object.values(context).some((v) => v !== undefined);

    try {
      const res = await chatAPI.send(message, hasContext ? context : undefined);
      setMessages((prev) => [...prev, {
        role: 'assistant', text: res.data.response, suggestions: res.data.suggestions,
        proposedAction: res.data.proposed_action || null,
      }]);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setMessages((prev) => [...prev, { role: 'assistant', text: detail || 'Unable to answer that right now. Please try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  // The assistant only ever prepares this - the real payment is created
  // here, at the moment the user explicitly clicks Confirm, via the same
  // authenticated/RBAC'd/audited endpoint the Payments page itself uses.
  const confirmAction = async (messageIndex, action) => {
    setLoading(true);
    try {
      if (action.action_type === 'record_payment') {
        await paymentsAPI.create(action.payload);
      }
      setMessages((prev) => prev.map((msg, i) => (
        i === messageIndex
          ? { ...msg, proposedAction: null, text: `${msg.text}\n\nDone - recorded.` }
          : msg
      )));
    } catch (err) {
      const detail = err.response?.data?.detail;
      setMessages((prev) => [...prev, { role: 'assistant', text: detail || 'That action failed. Please try again or use the page directly.' }]);
    } finally {
      setLoading(false);
    }
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
                  {m.proposedAction && (
                    <div className="chat-proposed-action">
                      <div className="chat-proposed-summary">{m.proposedAction.summary}</div>
                      <div className="chat-proposed-buttons">
                        <button className="btn-primary" onClick={() => confirmAction(i, m.proposedAction)} disabled={loading}>Confirm</button>
                        <button className="btn-secondary" onClick={() => dismissAction(i)} disabled={loading}>Not now</button>
                      </div>
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
                <div className="chat-bubble chat-assistant">Thinking...</div>
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
