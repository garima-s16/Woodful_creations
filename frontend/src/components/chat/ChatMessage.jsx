import React from 'react';
import '../../styles/components/chat/ChatMessage.css';

function ChatMessage({ message }) {
  const isUserMessage = message.sender === 'user';

  return (
    <div className={`chat-message ${message.sender}-message`}>
      <div className="message-content">
        {message.isError ? (
          <div className="message-error">{message.content}</div>
        ) : (
          <div className="message-text">{message.content}</div>
        )}
        
        {message.actionData && (
          <div className="message-action-data">
            <pre>{JSON.stringify(message.actionData, null, 2)}</pre>
          </div>
        )}
      </div>
      <div className="message-time">
        {new Date(message.timestamp).toLocaleTimeString([], { 
          hour: '2-digit', 
          minute: '2-digit' 
        })}
      </div>
    </div>
  );
}

export default ChatMessage;