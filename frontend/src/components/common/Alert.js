import React from 'react';
import './Alert.css';

const Alert = ({ type = 'info', message, onClose }) => {
  React.useEffect(() => {
    if (type !== 'error') {
      const timer = setTimeout(onClose, 5000);
      return () => clearTimeout(timer);
    }
  }, [type, onClose]);

  return (
    <div className={`alert alert-${type}`}>
      <div className="alert-content">{message}</div>
      <button className="alert-close" onClick={onClose}>&times;</button>
    </div>
  );
};

export default Alert;
