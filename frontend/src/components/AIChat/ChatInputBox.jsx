import React, { useState } from 'react';
import './ChatInputBox.css';

function ChatInputBox({ onSendMessage, isLoading }) {
  const [inputValue, setInputValue] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (inputValue.trim() && !isLoading) {
      onSendMessage(inputValue);
      setInputValue('');
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="chat-input-box">
      <textarea
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        onKeyPress={handleKeyPress}
        placeholder="Type your message here... (Shift+Enter for new line)"
        disabled={isLoading}
        className="chat-textarea"
        rows="2"
      />
      <button
        type="submit"
        disabled={isLoading || !inputValue.trim()}
        className="send-button"
      >
        {isLoading ? 'Sending...' : 'Send'}
      </button>
    </form>
  );
}

export default ChatInputBox;