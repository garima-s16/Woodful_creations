// Client Portal pages: Client Approval Hub (Family 137, feature 1) and
// My Order tracking (feature 3). Both are public - reached via a
// tokenized link, no login - and deliberately do NOT use the internal
// app's Sidebar/Navbar shell (see App.jsx: these routes render
// standalone, outside <Protected>).
import React, { useEffect, useState, useCallback } from 'react';
import { useParams } from 'react-router-dom';
import { clientPortalAPI } from '../../../utils/api';
import { Alert, Card, Form } from '../../../components/common/UI';
import { formatCurrency } from '../../../utils/utils';
import '../../../styles/modules.css';

function PortalShell({ children }) {
  return (
    <div className="client-portal-page">
      <div className="client-portal-container">
        <div className="client-portal-header">
          <img src="/logo-transparent.png" alt="Woodful Creations" className="client-portal-logo" />
          <h1>Woodful Creations</h1>
        </div>
        {children}
        <p className="client-portal-footer-note">
          Questions about this? Reply to the email this link came from, or call us directly.
        </p>
      </div>
    </div>
  );
}

// --- EstimateReviewPage.jsx (Client Approval Hub) ---
function EstimateReviewPage() {
  const { token } = useParams();
  const [estimate, setEstimate] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [loading, setLoading] = useState(true);
  const [decision, setDecision] = useState(null); // 'approve' | 'changes' | null
  const [submitting, setSubmitting] = useState(false);
  const [actionError, setActionError] = useState('');
  const [success, setSuccess] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    clientPortalAPI.getEstimate(token)
      .then((res) => { setEstimate(res.data); setLoadError(''); })
      .catch((err) => setLoadError(err.response?.data?.detail || 'This link is invalid or no longer active.'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const handleApprove = async (formData) => {
    setSubmitting(true);
    setActionError('');
    try {
      const res = await clientPortalAPI.approveEstimate(token, { name: formData.name, comments: formData.comments || null });
      setEstimate(res.data);
      setDecision(null);
      setSuccess('Thank you - your approval has been recorded.');
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRequestChanges = async (formData) => {
    setSubmitting(true);
    setActionError('');
    try {
      const res = await clientPortalAPI.requestEstimateChanges(token, { name: formData.name || null, comments: formData.comments });
      setEstimate(res.data);
      setDecision(null);
      setSuccess("Thanks - we've noted your requested changes and will follow up.");
    } catch (err) {
      setActionError(err.response?.data?.detail || 'Something went wrong. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <PortalShell><p>Loading...</p></PortalShell>;
  if (loadError) return <PortalShell><Alert type="error" message={loadError} onClose={() => {}} /></PortalShell>;
  if (!estimate) return null;

  return (
    <PortalShell>
      <Card title={`Estimate ${estimate.estimate_code}`}>
        <div className="card-body">
          <div className="client-portal-summary-row">
            <div className="client-portal-summary-item">
              <span className="label">Prepared for</span>
              <span className="value">{estimate.client_name}</span>
            </div>
            <div className="client-portal-summary-item">
              <span className="label">Total</span>
              <span className="value">{formatCurrency(estimate.total_cost)}</span>
            </div>
            {estimate.valid_until && (
              <div className="client-portal-summary-item">
                <span className="label">Valid until</span>
                <span className="value">{new Date(estimate.valid_until).toLocaleDateString()}</span>
              </div>
            )}
          </div>

          <div className="table-container">
            <table className="data-table">
              <thead><tr><th>Description</th><th>Qty</th><th>Rate</th><th>Amount</th></tr></thead>
              <tbody>
                {estimate.line_items.map((item, idx) => (
                  <tr key={idx}>
                    <td>{item.description}</td>
                    <td>{item.quantity} {item.unit}</td>
                    <td>{formatCurrency(item.rate)}</td>
                    <td>{formatCurrency(item.amount)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="client-portal-summary-row" style={{ marginTop: 16 }}>
            <div className="client-portal-summary-item"><span className="label">Subtotal</span><span className="value">{formatCurrency(estimate.subtotal)}</span></div>
            {estimate.discount > 0 && <div className="client-portal-summary-item"><span className="label">Discount</span><span className="value">-{formatCurrency(estimate.discount)}</span></div>}
            <div className="client-portal-summary-item"><span className="label">Tax ({estimate.tax_percent}%)</span><span className="value">{formatCurrency(estimate.tax_amount)}</span></div>
            <div className="client-portal-summary-item"><span className="label">Total</span><span className="value">{formatCurrency(estimate.total_cost)}</span></div>
          </div>

          {estimate.other_versions.length > 0 && (
            <p className="detail-meta-label" style={{ marginTop: 12 }}>
              Version {estimate.other_versions.length + 1} of this estimate. Earlier versions: {estimate.other_versions.map((v) => `v${v.version} (${v.status})`).join(', ')}.
            </p>
          )}

          {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}

          {estimate.status === 'approved' && (
            <Alert type="success" message={`Approved by ${estimate.approved_by} on ${new Date(estimate.approved_at).toLocaleDateString()}.`} onClose={() => {}} />
          )}
          {estimate.status === 'changes_requested' && !decision && (
            <Alert type="warning" message="You've requested changes on this estimate. We'll follow up shortly." onClose={() => {}} />
          )}
          {!estimate.can_decide && !['approved', 'changes_requested'].includes(estimate.status) && (
            <Alert type="info" message="This estimate is no longer awaiting a decision." onClose={() => {}} />
          )}

          {estimate.can_decide && !decision && (
            <div className="client-portal-actions">
              <button className="btn-primary" onClick={() => setDecision('approve')}>Approve</button>
              <button className="btn-secondary" onClick={() => setDecision('changes')}>Request Changes</button>
            </div>
          )}

          {actionError && <Alert type="error" message={actionError} onClose={() => setActionError('')} />}

          {decision === 'approve' && (
            <Form
              fields={[
                { name: 'name', label: 'Your name', required: true },
                { name: 'comments', label: 'Comments (optional)', type: 'textarea' },
              ]}
              onSubmit={handleApprove}
              loading={submitting}
              submitText="Confirm Approval"
              initialValues={{ name: '', comments: '' }}
            />
          )}
          {decision === 'changes' && (
            <Form
              fields={[
                { name: 'name', label: 'Your name (optional)' },
                { name: 'comments', label: 'What would you like changed?', type: 'textarea', required: true },
              ]}
              onSubmit={handleRequestChanges}
              loading={submitting}
              submitText="Send Request"
              initialValues={{ name: '', comments: '' }}
            />
          )}
        </div>
      </Card>
    </PortalShell>
  );
}

// --- MyOrderPage.jsx (My Order link) ---
function MyOrderPage() {
  const { token } = useParams();
  const [order, setOrder] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    clientPortalAPI.getOrder(token)
      .then((res) => setOrder(res.data))
      .catch((err) => setLoadError(err.response?.data?.detail || 'This link is invalid or no longer active.'))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <PortalShell><p>Loading...</p></PortalShell>;
  if (loadError) return <PortalShell><Alert type="error" message={loadError} onClose={() => {}} /></PortalShell>;
  if (!order) return null;

  const spec = order.approved_specification;

  return (
    <PortalShell>
      <Card title={`Order ${order.order_code}`}>
        <div className="card-body">
          <div className="client-portal-summary-row">
            <div className="client-portal-summary-item"><span className="label">Client</span><span className="value">{order.client_name}</span></div>
            <div className="client-portal-summary-item"><span className="label">Status</span><span className="value">{order.project_status}</span></div>
            <div className="client-portal-summary-item"><span className="label">Order date</span><span className="value">{new Date(order.order_date).toLocaleDateString()}</span></div>
            {order.delivery_date && (
              <div className="client-portal-summary-item"><span className="label">Expected delivery</span><span className="value">{new Date(order.delivery_date).toLocaleDateString()}</span></div>
            )}
          </div>

          <div className="client-portal-summary-row">
            <div className="client-portal-summary-item"><span className="label">Order value</span><span className="value">{formatCurrency(order.order_value)}</span></div>
            <div className="client-portal-summary-item"><span className="label">Amount paid</span><span className="value">{formatCurrency(order.amount_paid)}</span></div>
            <div className="client-portal-summary-item"><span className="label">Balance due</span><span className="value">{formatCurrency(order.outstanding_balance)}</span></div>
          </div>

          {spec && (
            <div style={{ marginTop: 16 }}>
              <span className="detail-meta-label">Approved Specification</span>
              <div className="detail-meta">
                {spec.material && <div className="detail-meta-item"><span className="detail-meta-label">Material</span><span className="detail-meta-value">{spec.material}</span></div>}
                {spec.finish && <div className="detail-meta-item"><span className="detail-meta-label">Finish</span><span className="detail-meta-value">{spec.finish}</span></div>}
                {spec.colour && <div className="detail-meta-item"><span className="detail-meta-label">Colour</span><span className="detail-meta-value">{spec.colour}</span></div>}
                {spec.hardware && <div className="detail-meta-item"><span className="detail-meta-label">Hardware</span><span className="detail-meta-value">{spec.hardware}</span></div>}
              </div>
            </div>
          )}

          {order.milestones.length > 0 && (
            <div style={{ marginTop: 16 }}>
              <span className="detail-meta-label">Progress</span>
              <div className="table-container">
                <table className="data-table">
                  <thead><tr><th>Milestone</th><th>Target</th><th>Completed</th></tr></thead>
                  <tbody>
                    {order.milestones.map((m, idx) => (
                      <tr key={idx}>
                        <td>{m.name}</td>
                        <td>{m.target_date ? new Date(m.target_date).toLocaleDateString() : '-'}</td>
                        <td>{m.completed_date ? new Date(m.completed_date).toLocaleDateString() : 'Pending'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      </Card>
    </PortalShell>
  );
}

export { EstimateReviewPage, MyOrderPage };
