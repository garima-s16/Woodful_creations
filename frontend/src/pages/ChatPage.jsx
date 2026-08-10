import React, { useState, useRef, useEffect } from 'react';
import { chatAPI } from '../utils/api';

function ChatPage() {
  const [messages, setMessages] = useState([
    { role: 'assistant', text: 'Hi! Ask me about stock, orders, clients, payments, or staff.', suggestions: ['Check low stock', 'Show pending orders', 'How many clients?'] },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

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
      setMessages((prev) => [...prev, { role: 'assistant', text: 'Something went wrong - please try again.' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    send();
  };

  return (
    <div className="page chat-page">
      <h1>Business Assistant</h1>
      <div className="chat-window">
        {messages.map((m, i) => (
          <div key={i} className={`chat-bubble chat-${m.role}`}>
            <div className="chat-text">{m.text}</div>
            {m.suggestions?.length > 0 && (
              <div className="chat-suggestions">
                {m.suggestions.map((s) => (
                  <button key={s} className="chat-suggestion" onClick={() => send(s)}>{s}</button>
                ))}
              </div>
            )}
          </div>
        ))}
        {loading && <div className="chat-bubble chat-assistant">Thinking...</div>}
        <div ref={endRef} />
      </div>
      <form className="chat-input-row" onSubmit={handleSubmit}>
        <input
          type="text" value={input} onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about stock, orders, clients, payments..." disabled={loading}
        />
        <button type="submit" className="btn-primary" disabled={loading}>Send</button>
      </form>
    </div>
  );
}

export default ChatPage;
