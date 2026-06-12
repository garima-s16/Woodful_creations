import React, { useState } from 'react';
import '../../styles/components/chat/ChatInput.css';

function ChatInput({ onSendMessage, disabled }) {
  const [inputValue, setInputValue] = useState('');

  const handleSend = () => {
    if (inputValue.trim() && !disabled) {
      onSendMessage(inputValue);
      setInputValue('');
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="chat-input-container">
      <textarea
        className="chat-input"
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyPress={handleKeyPress}
        placeholder="Type your message here... (Shift+Enter for new line)"
        disabled={disabled}
        rows="3"
      />
      <button 
        className="send-button"
        onClick={handleSend}
        disabled={disabled || !inputValue.trim()}
      >
        Send
      </button>
    </div>
  );
}

export default ChatInput;