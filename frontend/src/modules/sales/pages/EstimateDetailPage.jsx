import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { estimatesAPI, clientsAPI, ordersAPI, reportsAPI } from '../../../utils/api';
import Card from '../../../components/common/Card';
import Table from '../../../components/common/Table';
import Alert from '../../../components/common/Alert';
import Modal from '../../../components/common/Modal';
import SendEmailModal from '../../../components/common/SendEmailModal';
import Form from '../../../components/common/Form';
import { statusClass, formatCurrency, today } from '../../../utils/format';
import { classifyLoadError } from '../../../utils/loadError';


function EstimateDetailPage() {
  const { estimateId } = useParams();
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [estimate, setEstimate] = useState(null);
  const [client, setClient] = useState(null);
  const [order, setOrder] = useState(null);
  const [versions, setVersions] = useState([]);
  const [revising, setRevising] = useState(false);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState(null);
  const [versionsError, setVersionsError] = useState(false);
  const [showConvert, setShowConvert] = useState(false);
  const [showSendEmail, setShowSendEmail] = useState(false);
  const [sentMessage, setSentMessage] = useState('');
  const [converting, setConverting] = useState(false);
  const [convertError, setConvertError] = useState('');

  const load = useCallback(() => {
    setLoadError(null);
    estimatesAPI.get(estimateId).then((res) => {
      setEstimate(res.data);
      if (res.data.client_id) clientsAPI.get(res.data.client_id).then((r) => setClient(r.data)).catch(() => setClient('error'));
      if (res.data.order_id) ordersAPI.get(res.data.order_id).then((r) => setOrder(r.data)).catch(() => setOrder('error'));
    }).catch((err) => setLoadError(classifyLoadError(err, 'estimate')));
    setVersionsError(false);
    estimatesAPI.versions(estimateId).then((res) => setVersions(res.data)).catch(() => { setVersions([]); setVersionsError(true); });
  }, [estimateId]);

  useEffect(load, [load]);

  const handleRevise = async () => {
    setRevising(true);
    setError('');
    try {
      const res = await estimatesAPI.revise(estimateId);
      navigate(`/estimates/${res.data.id}`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create a new version');
    } finally {
      setRevising(false);
    }
  };

  const handleConvertToOrder = async (formData) => {
    setConverting(true);
    setConvertError('');
    try {
      const res = await ordersAPI.create({
        client_id: estimate.client_id,
        project_type: estimate.description ? estimate.description.slice(0, 100) : undefined,
        order_date: new Date(formData.order_date).toISOString(),
        advance: formData.advance || '0',
        from_estimate_id: estimate.id,
      });
      navigate(`/orders/${res.data.id}`);
    } catch (err) {
      setConvertError(err.response?.data?.detail || 'Failed to convert this estimate into an order');
    } finally {
      setConverting(false);
    }
  };

  if (loadError) return (
    <div className="page">
      <Alert type="error" message={loadError.message} />
      {!loadError.isNotFound && (
        <button type="button" className="btn-secondary" style={{ marginTop: 'var(--space-4)' }} onClick={load}>Retry</button>
      )}
    </div>
  );
  if (!estimate) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/estimates" className="btn-link">&larr; Back to Estimates</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{estimate.estimate_code}</h1>
          <div className="detail-subtitle">
            {client?.name || 'Client'} &middot; Version {estimate.version}
            {' '}<span className={`status-badge ${statusClass(estimate.status)}`}>{estimate.status}</span>
            {estimate.business_id && <span className="business-id-badge">{estimate.business_id}</span>}
          </div>
        </div>
        <div className="page-actions">
          {isPrivileged && (
            <button className="btn-secondary" onClick={handleRevise} disabled={revising}>
              {revising ? 'Creating...' : 'Create New Version'}
            </button>
          )}
          {isPrivileged && !estimate.order_id && estimate.status === 'approved' && (
            <button className="btn-primary" onClick={() => setShowConvert(true)}>Convert to Order</button>
          )}
          {isPrivileged && (
            <button className="btn-secondary" onClick={() => setShowSendEmail(true)}>Send to Client</button>
          )}
          <a className="btn-secondary" href={reportsAPI.downloadUrl(`estimates/${estimate.id}/quote.pdf`)} target="_blank" rel="noreferrer">
            Download Quote PDF
          </a>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {sentMessage && <Alert type="success" message={sentMessage} onClose={() => setSentMessage('')} />}

      <div className="kpi-row">
        {isPrivileged && (
          <>
            <Card><div className="card-body"><div className="detail-meta-label">Subtotal</div><h3>{formatCurrency(estimate.subtotal)}</h3></div></Card>
            <Card><div className="card-body"><div className="detail-meta-label">Discount</div><h3>{formatCurrency(estimate.discount)}</h3></div></Card>
            <Card><div className="card-body"><div className="detail-meta-label">Tax ({Number(estimate.tax_percent)}%)</div><h3>{formatCurrency(estimate.tax_amount)}</h3></div></Card>
            <Card><div className="card-body"><div className="detail-meta-label">Total Estimate</div><h3>{formatCurrency(estimate.total_cost)}</h3></div></Card>
          </>
        )}
      </div>

      {estimate.line_items?.length > 0 && (
        <Card title="Line Items">
          <Table
            columns={[
              { key: 'description', label: 'Description', render: (v, row) => (
                <>
                  {v}
                  {row.product_name && (
                    <div className="order-item-product-link">{row.product_code} &middot; {row.product_name}</div>
                  )}
                </>
              ) },
              { key: 'category', label: 'Category', render: (v) => v || '-' },
              { key: 'quantity', label: 'Qty', render: (v) => Number(v), align: 'right' },
              { key: 'unit', label: 'Unit', render: (v) => v || '-' },
              ...(isPrivileged ? [
                { key: 'rate', label: 'Rate', render: formatCurrency, align: 'right' },
                { key: 'amount', label: 'Amount', render: formatCurrency, align: 'right' },
              ] : []),
            ]}
            data={estimate.line_items}
          />
        </Card>
      )}

      <Card title="Estimate Details">
        <div className="card-body">
          <div className="detail-meta">
            <div className="detail-meta-item"><span className="detail-meta-label">Client</span><span className="detail-meta-value">{client === 'error' ? 'Unavailable' : client ? <Link to={`/clients/${client.id}`}>{client.name}</Link> : '-'}</span></div>
            <div className="detail-meta-item"><span className="detail-meta-label">Related Order</span><span className="detail-meta-value">{order === 'error' ? 'Unavailable' : order ? <Link to={`/orders/${order.id}`}>{order.order_code}</Link> : '-'}</span></div>
            <div className="detail-meta-item"><span className="detail-meta-label">Valid Until</span><span className="detail-meta-value">{estimate.valid_until ? new Date(estimate.valid_until).toLocaleDateString() : '-'}</span></div>
            <div className="detail-meta-item"><span className="detail-meta-label">Created</span><span className="detail-meta-value">{new Date(estimate.created_at).toLocaleDateString()}</span></div>
          </div>
          {estimate.description && (
            <div style={{ marginTop: 16 }}>
              <span className="detail-meta-label">Scope</span>
              <p>{estimate.description}</p>
            </div>
          )}
          {estimate.remarks && (
            <div style={{ marginTop: 16 }}>
              <span className="detail-meta-label">Remarks</span>
              <p>{estimate.remarks}</p>
            </div>
          )}
        </div>
      </Card>

      {(versions.length > 1 || versionsError) && (
        <Card title="Version History">
          <Table
            columns={[
              { key: 'version', label: 'Version' }, { key: 'estimate_code', label: 'Estimate Code' },
              { key: 'total_cost', label: 'Total', render: formatCurrency, align: 'right' },
              { key: 'status', label: 'Status', render: (v) => <span className={`status-badge ${statusClass(v)}`}>{v}</span> },
              { key: 'created_at', label: 'Created', render: (v) => new Date(v).toLocaleDateString() },
            ]}
            data={versions}
            error={versionsError}
            onRetry={load}
            onRowClick={(row) => navigate(`/estimates/${row.id}`)}
          />
        </Card>
      )}

      <Modal isOpen={showConvert} title="Convert to Order" onClose={() => { setShowConvert(false); setConvertError(''); }}>
        {convertError && <Alert type="error" message={convertError} onClose={() => setConvertError('')} />}
        <p style={{ marginBottom: 16, color: 'var(--text-secondary)', fontSize: '0.88rem' }}>
          This creates a new order for {client?.name || 'this client'} using this estimate's line items and total
          ({formatCurrency(estimate.total_cost)}). The estimate will be linked to the new order.
        </p>
        <Form
          fields={[
            { name: 'order_date', label: 'Order Date', type: 'date', required: true },
            { name: 'advance', label: 'Advance Received', type: 'number' },
          ]}
          onSubmit={handleConvertToOrder} loading={converting} submitText="Create Order"
          initialValues={{ order_date: today() }}
        />
      </Modal>
      <SendEmailModal
        isOpen={showSendEmail}
        title={`Send Estimate ${estimate.estimate_code}`}
        previewFn={() => estimatesAPI.emailPreview(estimateId)}
        sendFn={(data) => estimatesAPI.sendEmail(estimateId, data)}
        onClose={() => setShowSendEmail(false)}
        onSent={(message) => setSentMessage(message)}
      />
    </div>
  );
}

export default EstimateDetailPage;
