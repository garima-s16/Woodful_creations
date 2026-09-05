import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { estimatesAPI, clientsAPI, ordersAPI, reportsAPI } from '../../../utils/api';
import Table from '../../../components/common/Table';
import Modal from '../../../components/common/Modal';
import Form from '../../../components/common/Form';
import Alert from '../../../components/common/Alert';
import { formatCurrency } from '../../../utils/format';
import LineItemEditor, { emptyRow, quantityViolatesWholeUnitRule } from '../components/LineItemEditor';

function EstimatesPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [estimates, setEstimates] = useState([]);
  const [clients, setClients] = useState([]);
  const [orders, setOrders] = useState([]);
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [editingEstimate, setEditingEstimate] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [lineItems, setLineItems] = useState([emptyRow()]);
  const [selectedClientId, setSelectedClientId] = useState('');

  const load = () => {
    setPageLoading(true);
    setLoadError(false);
    estimatesAPI.list().then((res) => setEstimates(res.data)).catch(() => setLoadError(true)).finally(() => setPageLoading(false));
    clientsAPI.list().then((res) => setClients(res.data));
    ordersAPI.list().then((res) => setOrders(res.data));
  };
  useEffect(load, []);

  const handleCreate = async (formData) => {
    if (!selectedClientId) {
      setError('Please select a client first.');
      return;
    }
    const invalidRow = lineItems.find((row) => row.description.trim() && quantityViolatesWholeUnitRule(row.quantity, row.unit));
    if (invalidRow) {
      setError(`"${invalidRow.description}" - ${invalidRow.unit} must be a whole number, not a fractional quantity.`);
      return;
    }
    setLoading(true);
    setError('');
    const validItems = lineItems
      .filter((row) => row.description.trim())
      .map((row) => ({
        description: row.description, category: row.category || null,
        quantity: row.quantity || '1', unit: row.unit || null, rate: row.rate || '0',
        product_id: row.product_id ? Number(row.product_id) : null,
      }));
    try {
      await estimatesAPI.create({
        ...formData,
        client_id: Number(selectedClientId),
        order_id: formData.order_id ? Number(formData.order_id) : null,
        material_cost: formData.material_cost || '0',
        labor_cost: formData.labor_cost || '0',
        discount: formData.discount || '0',
        tax_percent: formData.tax_percent || '18',
        valid_until: formData.valid_until ? new Date(formData.valid_until).toISOString() : null,
        line_items: validItems,
      });
      setShowAdd(false);
      setLineItems([emptyRow()]);
      setSelectedClientId('');
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create estimate');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await estimatesAPI.update(editingEstimate.id, {
        material_cost: formData.material_cost, labor_cost: formData.labor_cost,
        tax_percent: formData.tax_percent, status: formData.status,
        valid_until: formData.valid_until ? new Date(formData.valid_until).toISOString() : null,
        remarks: formData.remarks,
      });
      setEditingEstimate(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update estimate');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'estimate_code', label: 'Estimate ID' },
    { key: 'client_id', label: 'Client', render: (v) => clients.find((c) => c.id === v)?.name || v },
    { key: 'subtotal', label: 'Subtotal', render: (v) => v != null ? formatCurrency(v) : 'Restricted' },
    { key: 'total_cost', label: 'Total', render: (v) => v != null ? formatCurrency(v) : 'Restricted' },
    { key: 'status', label: 'Status' },
    {
      key: 'quote_pdf', label: 'Quote', render: (v, row) => (
        <a href={reportsAPI.downloadUrl(`estimates/${row.id}/quote.pdf`)} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>Download PDF</a>
      ),
    },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        isPrivileged ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingEstimate(row); }}>Edit</button> : null
      ),
    },
  ];

  const createFields = [
    { name: 'order_id', label: 'Related Order (optional)', type: 'select', options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'description', label: 'Scope / Description', type: 'textarea' },
    { name: 'discount', label: 'Discount', type: 'number', placeholder: '0', advanced: true },
    { name: 'tax_percent', label: 'Tax % (GST)', type: 'number', placeholder: '18', advanced: true },
    { name: 'valid_until', label: 'Valid Until', type: 'date', advanced: true },
    { name: 'remarks', label: 'Remarks', type: 'textarea', advanced: true },
  ];

  const editFields = [
    { name: 'material_cost', label: 'Material Cost', type: 'number', required: true },
    { name: 'labor_cost', label: 'Labor Cost', type: 'number', required: true },
    { name: 'tax_percent', label: 'Tax %', type: 'number' },
    { name: 'status', label: 'Status', type: 'select', options: [
      { value: 'draft', label: 'Draft' }, { value: 'sent', label: 'Sent' },
      { value: 'approved', label: 'Approved' }, { value: 'rejected', label: 'Rejected' },
      { value: 'expired', label: 'Expired' }, { value: 'cancelled', label: 'Cancelled' },
    ] },
    { name: 'valid_until', label: 'Valid Until', type: 'date' },
    { name: 'remarks', label: 'Remarks', type: 'textarea' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Estimates</h1>
          <p className="page-summary">Prepare and track client quotations before they convert to orders.</p>
        </div>
        <div className="page-actions">
          {isPrivileged && <button className="btn-secondary" onClick={() => navigate('/estimates/import')}>Import Excel</button>}
          {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>New Estimate</button>}
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={estimates} loading={pageLoading} error={loadError} onRetry={load} onRowClick={(row) => navigate(`/estimates/${row.id}`)} emptyMessage="No estimates yet. Create your first estimate to get started." emptyAction={isPrivileged ? { label: 'New Estimate', onClick: () => setShowAdd(true) } : undefined} />
      <Modal isOpen={showAdd} title="New Estimate" size="wide" onClose={() => { setShowAdd(false); setSelectedClientId(''); setLineItems([emptyRow()]); }}>
        <div className="form-group">
          <label className="form-label">Client *</label>
          <select className="form-input" value={selectedClientId} onChange={(e) => setSelectedClientId(e.target.value)}>
            <option value="">Select a client...</option>
            {clients.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </div>
        <h4 style={{ marginBottom: 8 }}>Line Items</h4>
        <LineItemEditor items={lineItems} onChange={setLineItems} clientId={selectedClientId} />
        <Form fields={createFields} onSubmit={handleCreate} loading={loading} submitText="Create Estimate" />
      </Modal>
      <Modal isOpen={!!editingEstimate} title={`Edit ${editingEstimate?.estimate_code || ''}`} onClose={() => setEditingEstimate(null)}>
        {editingEstimate && (
          <Form
            fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes"
            initialValues={{
              material_cost: editingEstimate.material_cost, labor_cost: editingEstimate.labor_cost,
              tax_percent: editingEstimate.tax_percent, status: editingEstimate.status,
              valid_until: editingEstimate.valid_until ? editingEstimate.valid_until.slice(0, 10) : '',
              remarks: editingEstimate.remarks || '',
            }}
          />
        )}
      </Modal>
    </div>
  );
}

export default EstimatesPage;
