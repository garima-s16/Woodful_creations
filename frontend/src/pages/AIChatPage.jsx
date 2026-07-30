import React from 'react';
import ChatWidget from '../components/ChatWidget';

function AIChatPage() {
  return (
    <div className="page-container">
      <h1>AI Chat Assistant</h1>
      <div className="coming-soon-section">
        <p>Dedicated AI Chat Interface</p>
        <p>Ask questions about inventory, orders, clients, and business operations</p>
      </div>
      <ChatWidget />
    </div>
  );
}

export default AIChatPage;