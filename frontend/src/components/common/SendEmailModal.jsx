import React, { useState, useEffect } from 'react';
import Modal from './Modal';
import Alert from './Alert';

/**
 * previewFn: () => Promise<{data: {recipient_email, client_has_email, subject, body, attachment_filename}}>
 * sendFn: (payload: {recipient_email, subject, body}) => Promise<{data: {sent, message}}>
 * Both are called fresh each time the modal opens, since the underlying
 * record (and its client's email) may have changed since the page loaded.
 */
function SendEmailModal({ isOpen, title, previewFn, sendFn, onClose, onSent }) {
  const [loading, setLoading] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [preview, setPreview] = useState(null);
  const [recipientEmail, setRecipientEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');

  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    setError('');
    setPreview(null);
    previewFn()
      .then((res) => {
        setPreview(res.data);
        setRecipientEmail(res.data.recipient_email || '');
        setSubject(res.data.subject);
        setBody(res.data.body);
      })
      .catch((err) => setError(err.response?.data?.detail || 'Could not load a preview for this email.'))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const handleSend = async () => {
    if (!recipientEmail || !recipientEmail.includes('@')) {
      setError('Please enter a valid recipient email address.');
      return;
    }
    setSending(true);
    setError('');
    try {
      const res = await sendFn({ recipient_email: recipientEmail, subject, body });
      onSent && onSent(res.data.message);
      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'The email could not be sent. Please try again.');
    } finally {
      setSending(false);
    }
  };

  return (
    <Modal isOpen={isOpen} title={title} onClose={onClose}>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {loading && <p>Loading preview...</p>}
      {!loading && preview && (
        <div>
          {!preview.client_has_email && (
            <Alert type="warning" onClose={() => {}} message="This client has no email on file - please enter one below before sending." />
          )}
          <div className="form-group">
            <label className="form-label" htmlFor="send-email-to">To</label>
            <input
              id="send-email-to" className="form-input" type="email" value={recipientEmail}
              onChange={(e) => setRecipientEmail(e.target.value)} placeholder="client@example.com"
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="send-email-subject">Subject</label>
            <input
              id="send-email-subject" className="form-input" type="text" value={subject}
              onChange={(e) => setSubject(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="send-email-body">Message</label>
            <textarea
              id="send-email-body" className="form-input" rows={8} value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: 16 }}>
            Attachment: {preview.attachment_filename}
          </p>
          <div style={{ display: 'flex', gap: 12 }}>
            <button className="btn-primary" onClick={handleSend} disabled={sending}>
              {sending ? 'Sending...' : 'Send'}
            </button>
            <button className="btn-secondary" onClick={onClose} disabled={sending}>Cancel</button>
          </div>
        </div>
      )}
    </Modal>
  );
}

export default SendEmailModal;
