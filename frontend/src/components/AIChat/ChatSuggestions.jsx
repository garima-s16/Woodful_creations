import React from 'react';
import './ChatSuggestions.css';

function ChatSuggestions({ onSuggestionClick }) {
  const suggestions = [
    {
      id: 1,
      text: 'Show low stock items',
      description: 'View products below minimum stock level',
    },
    {
      id: 2,
      text: 'What are the top selling products?',
      description: 'Get top performing products analytics',
    },
    {
      id: 3,
      text: 'Show recent client orders',
      description: 'View latest orders from clients',
    },
    {
      id: 4,
      text: 'List all products',
      description: 'View complete product inventory',
    },
  ];

  return (
    <div className="suggestions-grid">
      {suggestions.map(suggestion => (
        <button
          key={suggestion.id}
          className="suggestion-card"
          onClick={() => onSuggestionClick(suggestion)}
        >
          <div className="suggestion-text">{suggestion.text}</div>
          <div className="suggestion-description">{suggestion.description}</div>
        </button>
      ))}
    </div>
  );
}

export default ChatSuggestions;