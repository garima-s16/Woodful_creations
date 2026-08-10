import React from 'react';
import './Card.css';

const Card = ({ title, children, actions, className = '' }) => {
  return (
    <div className={`card ${className}`}>
      {title && (
        <div className="card-header">
          <h3>{title}</h3>
          {actions && <div className="card-actions">{actions}</div>}
        </div>
      )}
      <div className="card-body">{children}</div>
    </div>
  );
};

export default Card;
