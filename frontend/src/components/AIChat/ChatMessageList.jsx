import React from 'react';
import './ChatMessageList.css';

function ChatMessageList({ messages }) {
  return (
    <div className="chat-messages">
      {messages.map(message => (
        <div
          key={message.id}
          className={`message message-${message.sender}`}
        >
          <div className="message-content">
            {message.sender === 'system' ? (
              <div className="message-text system-message">{message.text}</div>
            ) : (
              <>
                <div className="message-avatar">
                  {message.sender === 'ai' ? 'AI' : 'YOU'}
                </div>
                <div className="message-text">{message.text}</div>
              </>
            )}
          </div>
          <div className="message-time">
            {new Date(message.timestamp).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

export default ChatMessageList;