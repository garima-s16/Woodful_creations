import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import '../styles/pages/AIChatPage.css';
import ChatMessage from '../components/chat/ChatMessage';
import ChatInput from '../components/chat/ChatInput';

function AIChatPage({ user }) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef(null);

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const handleSendMessage = async (userMessage) => {
    if (!userMessage.trim()) return;

    setMessages(prev => [...prev, {
      id: Date.now(),
      content: userMessage,
      sender: 'user',
      timestamp: new Date()
    }]);

    setLoading(true);
    setError('');

    try {
      const token = localStorage.getItem('authToken');
      const response = await axios.post(
        `${API_BASE_URL}/api/chat/message`,
        { message: userMessage },
        { headers: { Authorization: `Bearer ${token}` } }
      );

      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        content: response.data.response,
        sender: 'ai',
        timestamp: new Date(),
        actionData: response.data.actionData
      }]);
    } catch (err) {
      setError('Failed to get response from AI');
      console.error(err);
      setMessages(prev => [...prev, {
        id: Date.now() + 1,
        content: 'Sorry, I encountered an error. Please try again.',
        sender: 'ai',
        timestamp: new Date(),
        isError: true
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ai-chat-page">
      <div className="chat-container">
        <div className="chat-header">
          <h1>AI Assistant</h1>
          <p>Ask me anything about your business</p>
        </div>

        <div className="chat-messages">
          {messages.length === 0 && (
            <div className="chat-welcome">
              <h2>Welcome to Woodful AI Chat</h2>
              <p>Try asking things like:</p>
              <ul>
                <li>Show me low stock items</li>
                <li>What are the pending payments?</li>
                <li>Generate a salary report</li>
                <li>Track client orders</li>
              </ul>
            </div>
          )}

          {messages.map(msg => (
            <ChatMessage key={msg.id} message={msg} />
          ))}

          {loading && (
            <div className="chat-message ai-message">
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          )}

          {error && (
            <div className="chat-error">
              {error}
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <ChatInput 
          onSendMessage={handleSendMessage}
          disabled={loading}
        />
      </div>
    </div>
  );
}

export default AIChatPage;