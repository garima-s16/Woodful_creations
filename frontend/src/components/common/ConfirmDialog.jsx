import React from 'react';
import Modal from './Modal';

/**
 * One reusable confirmation dialog for every destructive action in the
 * app (delete, remove, etc.) - built on the existing Modal component
 * so it inherits the same focus-trap/ESC-to-close/accessibility
 * handling, rather than every page implementing its own confirm logic
 * (e.g. window.confirm, which cannot be styled and does not match the
 * rest of the application).
 *
 * Usage: keep the "thing pending deletion" in state, render this with
 * isOpen={!!pendingDelete}, and call the real delete API only from
 * onConfirm.
 */
const ConfirmDialog = ({
  isOpen, title = 'Confirm', message = 'Are you sure you want to delete this?',
  confirmLabel = 'Delete', onConfirm, onCancel,
}) => (
  <Modal isOpen={isOpen} title={title} onClose={onCancel}>
    <p className="confirm-dialog-message">{message}</p>
    <div className="confirm-dialog-actions">
      <button type="button" className="btn-secondary" onClick={onCancel}>Cancel</button>
      <button type="button" className="btn-danger" onClick={onConfirm}>{confirmLabel}</button>
    </div>
  </Modal>
);

export default ConfirmDialog;
