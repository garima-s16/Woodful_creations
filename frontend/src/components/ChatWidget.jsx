import React, { useState, useRef, useEffect } from 'react';
import { chatAPI } from '../utils/api';
import AssistantMascot from './AssistantMascot';
import '../styles/components/ChatWidget.css';

function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([
    { role: 'assistant', text: 'Hi, I\'m the Woodful Assistant. Ask me about stock, orders, clients, payments, or staff.', suggestions: ['Check Low Stock', 'Show Outstanding Payments', 'Show Active Orders', "Today's Tasks"] },
  ]);
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
    try {
      const res = await chatAPI.send(message);
      setMessages((prev) => [...prev, { role: 'assistant', text: res.data.response, suggestions: res.data.suggestions }]);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setMessages((prev) => [...prev, { role: 'assistant', text: detail || 'Unable to answer that right now. Please try again.' }]);
    } finally {
      setLoading(false);
    }
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
