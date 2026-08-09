import React, { useState } from 'react';
import './Modal.css';

const Modal = ({ isOpen, title, children, onClose, onSubmit, submitText = 'Submit', loading = false }) => {
  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>{title}</h2>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">{children}</div>
        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose} disabled={loading}>
            Cancel
          </button>
          {onSubmit && (
            <button
              className="btn-primary"
              onClick={onSubmit}
              disabled={loading}
            >
              {loading ? 'Loading...' : submitText}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default Modal;
