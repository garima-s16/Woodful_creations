import React, { useEffect, useRef, useId } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import './Modal.css';

const Modal = ({ isOpen, title, children, onClose, size }) => {
  const contentRef = useRef(null);
  const previouslyFocusedRef = useRef(null);
  const titleId = useId();

  // Move focus into the modal on open, and back to whatever triggered it
  // on close - without this, keyboard/screen-reader users lose their
  // place in the page every time a modal opens or closes.
  useEffect(() => {
    if (!isOpen) return undefined;

    previouslyFocusedRef.current = document.activeElement;
    const firstFocusable = contentRef.current?.querySelector(
      'input, select, textarea, button, [href], [tabindex]:not([tabindex="-1"])'
    );
    (firstFocusable || contentRef.current)?.focus();

    return () => {
      previouslyFocusedRef.current?.focus?.();
    };
  }, [isOpen]);

  // ESC to close, and a simple Tab focus trap so keyboard focus can't
  // silently leave the modal into the (visually dimmed) page behind it.
  useEffect(() => {
    if (!isOpen) return undefined;

    function handleKeyDown(event) {
      if (event.key === 'Escape') {
        onClose();
        return;
      }
      if (event.key === 'Tab' && contentRef.current) {
        const focusable = contentRef.current.querySelectorAll(
          'input, select, textarea, button, [href], [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          className="modal-overlay"
          onClick={onClose}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.16, ease: 'easeOut' }}
        >
          <motion.div
            className={`modal-content${size === 'wide' ? ' modal-content--wide' : ''}`}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            ref={contentRef}
            tabIndex={-1}
            onClick={(e) => e.stopPropagation()}
            initial={{ opacity: 0, y: 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
          >
            <div className="modal-header">
              <h2 id={titleId}>{title}</h2>
              <button className="modal-close" onClick={onClose} aria-label="Close dialog">&times;</button>
            </div>
            <div className="modal-body">{children}</div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default Modal;
