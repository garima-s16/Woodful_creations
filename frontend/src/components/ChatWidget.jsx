import React, { useState, useRef, useEffect } from 'react';
import { chatAPI } from '../utils/api';
import '../styles/ChatWidget.css';

function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    {
      id: 1,
      type: 'bot',
      text: 'Hello! I am Woodful AI Assistant. How can I help you with inventory, estimates, or business queries?',
      timestamp: new Date(),
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = {
      id: Date.now(),
      type: 'user',
      text: input,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setLoading(true);

    try {
      const conversationId = localStorage.getItem('userId');
      const response = await chatAPI.sendMessage(input, conversationId);

      const botMessage = {
        id: Date.now() + 1,
        type: 'bot',
        text: response.data.response || 'I could not process your request. Please try again.',
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage = {
        id: Date.now() + 1,
        type: 'bot',
        text: 'Sorry, I am having trouble connecting. Please try again later.',
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <button
        className="chat-widget-toggle"
        onClick={() => setIsOpen(!isOpen)}
        title="Open AI Chat"
      >
        Chat
      </button>

      {isOpen && (
        <div className="chat-widget-container">
          <div className="chat-widget-header">
            <h3>Woodful AI Assistant</h3>
            <button
              className="chat-close-btn"
              onClick={() => setIsOpen(false)}
              title="Close"
            >
              X
            </button>
          </div>

          <div className="chat-widget-messages">
            {messages.map((msg) => (
              <div key={msg.id} className={`chat-message ${msg.type}`}>
                <div className="chat-message-content">{msg.text}</div>
              </div>
            ))}
            {loading && (
              <div className="chat-message bot">
                <div className="chat-message-content typing">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <form className="chat-widget-form" onSubmit={handleSendMessage}>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Type your message..."
              disabled={loading}
            />
            <button type="submit" disabled={loading}>
              Send
            </button>
          </form>
        </div>
      )}
    </>
  );
}

export default ChatWidget;