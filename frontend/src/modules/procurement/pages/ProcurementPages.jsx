// Procurement pages: suppliers list/detail, purchases list/detail,
// and purchase Excel import. Combines the former SuppliersPage.jsx,
// SupplierDetailPage.jsx, PurchasesPage.jsx, PurchaseDetailPage.jsx,
// and PurchaseImportPage.jsx.
import React, { useCallback, useEffect, useState } from 'react';
import { Link, useLocation, useNavigate, useParams } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { documentsAPI, locationsAPI, materialsAPI, purchaseImportAPI, purchasesAPI, reportsAPI, suppliersAPI } from '../../../utils/api';
import { Alert, Card, ConfirmDialog, Form, KpiCard, Modal, Table } from '../../../components/common/UI';
import { DocumentsPanel } from '../../../components/Assistant';
import { classifyLoadError, formatCurrency, statusClass, today } from '../../../utils/utils';

// --- SuppliersPage.jsx ---
function SuppliersPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const isStrictlyMaster = user?.role === 'master';
  const [suppliers, setSuppliers] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [editingSupplier, setEditingSupplier] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = () => {
    setPageLoading(true);
    setLoadError(false);
    suppliersAPI.list().then((res) => setSuppliers(res.data)).catch(() => setLoadError(true)).finally(() => setPageLoading(false));
  };
  useEffect(() => {
    load();
  }, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await suppliersAPI.create(formData);
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add supplier');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await suppliersAPI.update(editingSupplier.id, formData);
      setEditingSupplier(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update supplier');
    } finally {
      setLoading(false);
    }
  };

  const [pendingDelete, setPendingDelete] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const handleDelete = (supplier) => setPendingDelete(supplier);
  const confirmDelete = async () => {
    setError('');
    setDeleting(true);
    try {
      await suppliersAPI.remove(pendingDelete.id);
      setPendingDelete(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete supplier');
      setPendingDelete(null);
    } finally {
      setDeleting(false);
    }
  };

  const columns = [
    { key: 'supplier_code', label: 'Supplier ID' }, { key: 'name', label: 'Name' },
    { key: 'category', label: 'Category' }, { key: 'contact_person', label: 'Contact Person' },
    { key: 'phone', label: 'Phone' }, { key: 'payment_terms', label: 'Payment Terms' },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        isPrivileged ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingSupplier(row); }}>Edit</button> : null
      ),
    },
    {
      key: 'delete_action', label: '', render: (v, row) => (
        isStrictlyMaster ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); handleDelete(row); }}>Delete</button> : null
      ),
    },
  ];

  const fields = [
    { name: 'name', label: 'Name', required: true },
    { name: 'category', label: 'Category' },
    { name: 'phone', label: 'Phone', hint: 'Exactly 10 digits.',
      validate: (value) => (/^[0-9]{10}$/.test(value) ? '' : 'Please enter valid mobile number') },
    { name: 'contact_person', label: 'Contact Person', advanced: true },
    {
      name: 'gstin', label: 'GSTIN', advanced: true,
      hint: '15-character GST identification number',
      validate: (value) => (value.length !== 15 ? 'GSTIN must contain 15 characters.' : null),
    },
    { name: 'payment_terms', label: 'Payment Terms', advanced: true },
    { name: 'remarks', label: 'Remarks', type: 'textarea', advanced: true },
  ];

  const editFields = fields.filter((f) => f.name !== 'supplier_code');

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Suppliers</h1>
          <p className="page-summary">Track supplier relationships and purchase history.</p>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('suppliers.xlsx')} target="_blank" rel="noreferrer">
            Export Excel
          </a>
          {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Supplier</button>}
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <div className="kpi-row">
        <KpiCard label="Total Suppliers" value={suppliers.length} />
      </div>
      <Table
        columns={columns} data={suppliers} loading={pageLoading} error={loadError} onRetry={load}
        onRowClick={(row) => navigate(`/suppliers/${row.id}`)}
        emptyMessage="No suppliers added yet. Add your first supplier to start managing purchase relationships."
        emptyAction={isPrivileged ? { label: 'Add Supplier', onClick: () => setShowAdd(true) } : undefined}
      />
      <Modal isOpen={showAdd} title="Add Supplier" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Add Supplier" />
      </Modal>
      <Modal isOpen={!!editingSupplier} title={`Edit ${editingSupplier?.name || ''}`} onClose={() => setEditingSupplier(null)}>
        {editingSupplier && (
          <Form fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes" initialValues={editingSupplier} />
        )}
      </Modal>

      <ConfirmDialog
        isOpen={!!pendingDelete}
        message={pendingDelete ? `Delete ${pendingDelete.name}? This cannot be undone.` : ''}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
        loading={deleting}
      />
    </div>
  );
}

// --- SupplierDetailPage.jsx ---
function SupplierDetailPage() {
  const { supplierId } = useParams();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [supplier, setSupplier] = useState(null);
  const [purchases, setPurchases] = useState([]);
  const [purchasesError, setPurchasesError] = useState(false);
  const [loadError, setLoadError] = useState('');

  const load = useCallback(() => {
    setLoadError('');
    setPurchasesError(false);
    suppliersAPI.get(supplierId).then((res) => setSupplier(res.data)).catch(() => setLoadError('Unable to load this supplier.'));
    purchasesAPI.list({ supplier_id: supplierId }).then((res) => setPurchases(res.data)).catch(() => { setPurchases([]); setPurchasesError(true); });
  }, [supplierId]);

  useEffect(load, [load]);

  if (loadError) return <div className="page"><Alert type="error" message={loadError} /><button type="button" className="btn-secondary" style={{ marginTop: 'var(--space-4)' }} onClick={load}>Retry</button></div>;
  if (!supplier) return <div className="page">Loading...</div>;

  const totalPurchased = purchases.reduce((sum, p) => sum + Number(p.invoice_total || 0), 0);
  const outstanding = purchases.filter((p) => p.payment_status !== 'Paid');

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/suppliers" className="btn-link">&larr; Back to Suppliers</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{supplier.name}</h1>
          <div className="detail-subtitle">
            {supplier.supplier_code} &middot; {supplier.category || 'Uncategorized'}
            {supplier.business_id && <span className="business-id-badge">{supplier.business_id}</span>}
          </div>
        </div>
      </div>

      <div className="kpi-row">
        {isPrivileged && (
          <>
            <Card><div className="card-body"><div className="detail-meta-label">Total Purchased</div><h3>{formatCurrency(totalPurchased)}</h3></div></Card>
            <Card><div className="card-body"><div className="detail-meta-label">Purchase Count</div><h3>{purchases.length}</h3></div></Card>
            <Card><div className="card-body"><div className="detail-meta-label">Unpaid/Part Paid Invoices</div><h3>{outstanding.length}</h3></div></Card>
          </>
        )}
        <Card><div className="card-body"><div className="detail-meta-label">Payment Terms</div><h3 style={{ fontSize: '1.1rem' }}>{supplier.payment_terms || '-'}</h3></div></Card>
      </div>

      <Card title="Supplier Details">
        <div className="card-body">
          <div className="detail-meta">
            <div className="detail-meta-item"><span className="detail-meta-label">Contact Person</span><span className="detail-meta-value">{supplier.contact_person || '-'}</span></div>
            <div className="detail-meta-item"><span className="detail-meta-label">Phone</span><span className="detail-meta-value">{supplier.phone ? <a href={`tel:${supplier.phone}`}>{supplier.phone}</a> : '-'}</span></div>
            <div className="detail-meta-item"><span className="detail-meta-label">GSTIN</span><span className="detail-meta-value">{supplier.gstin || '-'}</span></div>
          </div>
        </div>
      </Card>

      {isPrivileged && (
        <Card title="Purchase History">
          <Table
            columns={[
              { key: 'purchase_code', label: 'Purchase' },
              { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
              { key: 'quantity', label: 'Quantity', align: 'right' }, { key: 'invoice_total', label: 'Invoice Total', render: formatCurrency, align: 'right' },
              { key: 'payment_status', label: 'Payment Status' },
            ]}
            data={purchases}
            error={purchasesError}
            onRetry={load}
            emptyMessage="No purchases recorded from this supplier yet."
          />
        </Card>
      )}

      <DocumentsPanel title="Documents" api={{
        list: () => documentsAPI.list('supplier', supplierId),
        upload: (file, description) => documentsAPI.upload('supplier', supplierId, file, description),
        downloadUrl: (documentId) => documentsAPI.downloadUrl('supplier', supplierId, documentId),
        remove: (documentId) => documentsAPI.remove('supplier', supplierId, documentId),
      }} canUpload={isPrivileged} />
    </div>
  );
}

// --- PurchasesPage.jsx ---
function PurchasesPage() {
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [purchases, setPurchases] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [locations, setLocations] = useState([]);
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate && !location.state?.bulkRows);
  const [showBulkAdd, setShowBulkAdd] = useState(!!location.state?.bulkRows?.length);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = () => {
    setPageLoading(true);
    setLoadError(false);
    purchasesAPI.list().then((res) => setPurchases(res.data)).catch((err) => {
      setLoadError(true);
      setError(err.response?.status === 403 ? 'You do not have permission to view purchases.' : 'Unable to load purchases. Please try again.');
    }).finally(() => setPageLoading(false));
    suppliersAPI.list().then((res) => setSuppliers(res.data));
    materialsAPI.list().then((res) => setMaterials(res.data));
    locationsAPI.list().then((res) => setLocations(res.data)).catch(() => setLocations([]));
  };
  useEffect(load, []);

  const handleReceive = async (purchaseId) => {
    setError('');
    try {
      await purchasesAPI.receive(purchaseId);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to mark this purchase as received');
    }
  };

  const [pendingDeletePurchase, setPendingDeletePurchase] = useState(null);
  const [deletingPurchase, setDeletingPurchase] = useState(false);
  const handleDeletePurchase = async () => {
    if (!pendingDeletePurchase) return;
    setDeletingPurchase(true);
    setError('');
    try {
      await purchasesAPI.remove(pendingDeletePurchase.id);
      setPendingDeletePurchase(null);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete this purchase.');
      setPendingDeletePurchase(null);
    } finally {
      setDeletingPurchase(false);
    }
  };

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      // unit is a display-only "computed" field (see its definition
      // below) - Form.js never writes a computed field's value into
      // formData, so the actual request must derive it here too, from
      // the same source, or the submitted purchase would carry a
      // missing/blank unit.
      const selectedMaterial = materials.find((m) => String(m.id) === String(formData.material_id));
      await purchasesAPI.create({
        ...formData,
        supplier_id: Number(formData.supplier_id),
        material_id: Number(formData.material_id),
        quantity: formData.quantity, rate: formData.rate, unit: selectedMaterial?.unit || '',
        gst_percent: formData.gst_percent || '18',
        location_id: formData.location_id ? Number(formData.location_id) : null,
        date: new Date(formData.date).toISOString(),
      });
      setShowAdd(false);
      setSuccess('Purchase saved.');
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to record purchase');
    } finally {
      setLoading(false);
    }
  };

  const emptyBulkRow = () => ({ material_id: '', quantity: '', rate: '', unit: '', location_id: '' });
  const [bulkSupplierId, setBulkSupplierId] = useState(location.state?.bulkRows?.[0]?.supplier_id || '');
  const [bulkDate, setBulkDate] = useState(today());
  const [bulkGstPercent, setBulkGstPercent] = useState('18');
  const [bulkPaymentStatus, setBulkPaymentStatus] = useState('Paid');
  const [bulkReceiptStatus, setBulkReceiptStatus] = useState('Received');
  const [bulkRows, setBulkRows] = useState(
    location.state?.bulkRows?.length
      ? location.state.bulkRows.map((r) => ({
          material_id: r.material_id || '', quantity: r.quantity || '', rate: r.rate || '',
          unit: r.unit || '', location_id: '',
        }))
      : [emptyBulkRow()]
  );
  const updateBulkRow = (index, field, value) => {
    setBulkRows((rows) => rows.map((r, i) => {
      if (i !== index) return r;
      const updated = { ...r, [field]: value };
      if (field === 'material_id') {
        const material = materials.find((m) => m.id === Number(value));
        if (material?.unit) updated.unit = material.unit;
      }
      return updated;
    }));
  };
  const addBulkRow = () => setBulkRows((rows) => [...rows, emptyBulkRow()]);
  const removeBulkRow = (index) => setBulkRows((rows) => rows.filter((_, i) => i !== index));

  const handleBulkCreate = async () => {
    setLoading(true);
    setError('');
    const validRows = bulkRows.filter((r) => r.material_id && r.quantity && r.rate && r.unit);
    if (!bulkSupplierId || validRows.length === 0) {
      setError('Pick a supplier and fill in at least one complete material row (material, quantity, rate, unit).');
      setLoading(false);
      return;
    }
    let created = 0;
    for (const row of validRows) {
      try {
        await purchasesAPI.create({
          supplier_id: Number(bulkSupplierId), material_id: Number(row.material_id),
          quantity: row.quantity, rate: row.rate, unit: row.unit,
          gst_percent: bulkGstPercent || '18',
          location_id: row.location_id ? Number(row.location_id) : null,
          date: new Date(bulkDate).toISOString(),
          payment_status: bulkPaymentStatus, receipt_status: bulkReceiptStatus,
        });
        created += 1;
      } catch (err) {
        setError(`Created ${created} of ${validRows.length} purchases, then stopped: ${err.response?.data?.detail || 'a purchase failed to save'}. The successfully-created ones above are already saved - fix the remaining rows and try again for just those.`);
        setLoading(false);
        load();
        return;
      }
    }
    setShowBulkAdd(false);
    setSuccess(`${created} purchase${created === 1 ? '' : 's'} saved from ${suppliers.find((s) => s.id === Number(bulkSupplierId))?.name || 'the supplier'}.`);
    setLoading(false);
    load();
  };
  const columns = [
    { key: 'purchase_code', label: 'Purchase ID' },
    { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
    { key: 'supplier_id', label: 'Supplier', render: (v) => suppliers.find((s) => s.id === v)?.name || v },
    { key: 'material_id', label: 'Material', render: (v) => materials.find((m) => m.id === v)?.name || v },
    { key: 'quantity', label: 'Quantity' }, { key: 'unit', label: 'Unit' }, { key: 'rate', label: 'Rate' },
    { key: 'invoice_total', label: 'Invoice Total', render: (v) => formatCurrency(v) },
    { key: 'payment_status', label: 'Payment Status' },
    { key: 'receipt_status', label: 'Receipt Status', render: (v) => (
      <span className={`status-badge ${statusClass(v)}`}>{v}</span>
    ) },
    { key: 'actions', label: '', render: (_, row) => (
      <>
        {row.receipt_status === 'Ordered' && (
          <button className="btn-link" onClick={(e) => { e.stopPropagation(); handleReceive(row.id); }}>Mark Received</button>
        )}
        {row.receipt_status !== 'Received' && (
          <button className="btn-link" onClick={(e) => { e.stopPropagation(); setPendingDeletePurchase(row); }}>Delete</button>
        )}
      </>
    ) },
  ];

  const fields = [
    { name: 'supplier_id', label: 'Supplier', type: 'select', required: true, section: 'Supplier & Invoice', options: suppliers.map((s) => ({ value: s.id, label: s.name })) },
    { name: 'date', label: 'Date', type: 'date', required: true, section: 'Supplier & Invoice' },
    { name: 'material_id', label: 'Material', type: 'select', required: true, section: 'Material', options: materials.map((m) => ({ value: m.id, label: m.name })) },
    { name: 'quantity', label: 'Quantity', type: 'number', required: true, section: 'Quantity & Cost' },
    {
      name: 'unit', label: 'Unit', section: 'Quantity & Cost', type: 'computed',
      // Genuinely locked to the selected Material's own recorded unit
      // - never free-typed (matches the same fix in InventoryPage.jsx's
      // Receive Stock wizard).
      compute: (formData) => materials.find((m) => String(m.id) === String(formData.material_id))?.unit || '',
    },
    { name: 'rate', label: 'Rate', type: 'number', required: true, section: 'Quantity & Cost' },
    { name: 'location_id', label: 'Receiving Location', type: 'select', section: 'Quantity & Cost',
      options: locations.map((l) => ({ value: l.id, label: l.full_path })), placeholder: "Material's primary location" },
    { name: 'gst_percent', label: 'GST %', type: 'number', placeholder: '18', section: 'Tax' },
    { name: 'payment_status', label: 'Payment Status', type: 'select', section: 'Payment', options: [
      { value: 'Paid', label: 'Paid' }, { value: 'Part Paid', label: 'Part Paid' }, { value: 'Credit', label: 'Credit' },
    ] },
    { name: 'receipt_status', label: 'Receipt Status', type: 'select', section: 'Payment', options: [
      { value: 'Received', label: 'Received - stock updates immediately' },
      { value: 'Ordered', label: 'Ordered - not yet arrived, stock stays unchanged until received' },
    ] },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Purchases (Stock In)</h1>
          <p className="page-summary">Record material receipts from suppliers and keep purchase history in one place.</p>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('purchases.xlsx')} target="_blank" rel="noreferrer">Export</a>
          {isPrivileged && <a className="btn-secondary" href={purchaseImportAPI.templateUrl}>Download Template</a>}
          {isPrivileged && <button className="btn-secondary" onClick={() => navigate('/purchases/import')}>Import Excel</button>}
          {isPrivileged && <button className="btn-secondary" onClick={() => setShowBulkAdd(true)}>Buy Multiple Items</button>}
          {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Record Purchase</button>}
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      {success && <Alert type="success" message={success} onClose={() => setSuccess('')} />}
      <Table columns={columns} data={purchases} loading={pageLoading} error={loadError} onRetry={load} onRowClick={(row) => navigate(`/purchases/${row.id}`)} emptyMessage="No purchases recorded yet. Record your first purchase to start tracking inventory." emptyAction={isPrivileged ? { label: 'Record Purchase', onClick: () => setShowAdd(true) } : undefined} />

      <ConfirmDialog
        isOpen={!!pendingDeletePurchase}
        title="Delete Purchase"
        message={pendingDeletePurchase ? `Delete ${pendingDeletePurchase.purchase_code}? This cannot be undone.` : ''}
        onConfirm={handleDeletePurchase}
        onCancel={() => setPendingDeletePurchase(null)}
        loading={deletingPurchase}
      />
      <Modal isOpen={showAdd} title="Record Purchase" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Record Purchase"
          initialValues={{ date: today(), ...(location.state?.prefill || {}) }} />
      </Modal>
      <Modal isOpen={showBulkAdd} title="Buy Multiple Items From One Supplier" onClose={() => setShowBulkAdd(false)}>
        <div className="bulk-purchase-form">
          <p className="page-summary" style={{ marginBottom: 'var(--space-4)' }}>
            One supplier, one invoice date - as many materials as you need. Each row is saved as its own purchase record.
          </p>
          <div className="bulk-purchase-shared-fields">
            <label>
              Supplier
              <select value={bulkSupplierId} onChange={(e) => setBulkSupplierId(e.target.value)}>
                <option value="">Select supplier...</option>
                {suppliers.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            </label>
            <label>
              Date
              <input type="date" value={bulkDate} onChange={(e) => setBulkDate(e.target.value)} />
            </label>
            <label>
              GST %
              <input type="number" value={bulkGstPercent} onChange={(e) => setBulkGstPercent(e.target.value)} placeholder="18" />
            </label>
            <label>
              Payment Status
              <select value={bulkPaymentStatus} onChange={(e) => setBulkPaymentStatus(e.target.value)}>
                <option value="Paid">Paid</option>
                <option value="Part Paid">Part Paid</option>
                <option value="Credit">Credit</option>
              </select>
            </label>
            <label>
              Receipt Status
              <select value={bulkReceiptStatus} onChange={(e) => setBulkReceiptStatus(e.target.value)}>
                <option value="Received">Received - stock updates immediately</option>
                <option value="Ordered">Ordered - not yet arrived</option>
              </select>
            </label>
          </div>

          <div className="bulk-purchase-rows">
            {bulkRows.map((row, i) => (
              <div className="bulk-purchase-row" key={i}>
                <select value={row.material_id} onChange={(e) => updateBulkRow(i, 'material_id', e.target.value)}>
                  <option value="">Select material...</option>
                  {materials.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
                </select>
                <input type="number" placeholder="Qty" value={row.quantity} onChange={(e) => updateBulkRow(i, 'quantity', e.target.value)} />
                <input placeholder="Unit" value={row.unit} readOnly disabled className="form-input-readonly" title="Set automatically from the selected material" />
                <input type="number" placeholder="Rate" value={row.rate} onChange={(e) => updateBulkRow(i, 'rate', e.target.value)} />
                <select value={row.location_id} onChange={(e) => updateBulkRow(i, 'location_id', e.target.value)}>
                  <option value="">Location...</option>
                  {locations.map((l) => <option key={l.id} value={l.id}>{l.full_path}</option>)}
                </select>
                <button type="button" className="cart-drawer-remove" onClick={() => removeBulkRow(i)} aria-label="Remove row" disabled={bulkRows.length === 1}>
                  &times;
                </button>
              </div>
            ))}
          </div>
          <button type="button" className="btn-secondary" onClick={addBulkRow}>+ Add Another Material</button>

          <div className="bulk-purchase-actions">
            <button type="button" className="btn-primary" onClick={handleBulkCreate} disabled={loading}>
              {loading ? 'Saving...' : `Save ${bulkRows.filter((r) => r.material_id && r.quantity && r.rate && r.unit).length || ''} Purchase${bulkRows.length === 1 ? '' : 's'}`}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}

// --- PurchaseDetailPage.jsx ---
function PurchaseDetailPage() {
  const { purchaseId } = useParams();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [purchase, setPurchase] = useState(null);
  const [supplier, setSupplier] = useState(null);
  const [material, setMaterial] = useState(null);
  const [error, setError] = useState('');
  const [loadError, setLoadError] = useState(null);

  const load = useCallback(() => {
    setLoadError(null);
    purchasesAPI.get(purchaseId).then((res) => {
      setPurchase(res.data);
      if (res.data.supplier_id) suppliersAPI.get(res.data.supplier_id).then((r) => setSupplier(r.data)).catch(() => setSupplier('error'));
      if (res.data.material_id) materialsAPI.get(res.data.material_id).then((r) => setMaterial(r.data)).catch(() => setMaterial('error'));
    }).catch((err) => setLoadError(classifyLoadError(err, 'purchase')));
  }, [purchaseId]);

  useEffect(load, [load]);

  const handleReceive = async () => {
    setError('');
    try {
      await purchasesAPI.receive(purchaseId);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to mark this purchase as received');
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
  if (!purchase) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{purchase.purchase_code}</h1>
          <div className="detail-subtitle">
            {supplier === 'error' ? 'Supplier unavailable' : (supplier?.name || 'Supplier')} &middot; {material === 'error' ? 'Material unavailable' : (material?.name || 'Material')}
            {' '}<span className={`status-badge ${purchase.receipt_status === 'Ordered' ? 'status-warning' : 'status-ok'}`}>{purchase.receipt_status}</span>
            {purchase.business_id && <span className="business-id-badge">{purchase.business_id}</span>}
          </div>
        </div>
        {purchase.receipt_status === 'Ordered' && (
          <div className="detail-header-actions">
            <button className="btn-primary" onClick={handleReceive}>Mark Received</button>
          </div>
        )}
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <div className="kpi-row">
        <Card><div className="card-body"><div className="detail-meta-label">Quantity</div><h3>{Number(purchase.quantity)} {purchase.unit}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Rate</div><h3>{formatCurrency(purchase.rate)}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">GST ({Number(purchase.gst_percent)}%)</div><h3>{formatCurrency(purchase.gst_amount)}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Invoice Total</div><h3>{formatCurrency(purchase.invoice_total)}</h3></div></Card>
      </div>

      <Card title="Purchase Details">
        <div className="card-body">
          <div className="detail-meta">
            <div className="detail-meta-item">
              <span className="detail-meta-label">Date</span>
              <span className="detail-meta-value">{new Date(purchase.date).toLocaleDateString()}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Supplier</span>
              <span className="detail-meta-value">{supplier === 'error' ? 'Unavailable' : (supplier?.name || '-')}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Material</span>
              <span className="detail-meta-value">{material === 'error' ? 'Unavailable' : (material?.name || '-')}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Taxable Value</span>
              <span className="detail-meta-value">{formatCurrency(purchase.taxable_value)}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Payment Status</span>
              <span className={`status-badge ${statusClass(purchase.payment_status)}`}>{purchase.payment_status}</span>
            </div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Receipt Status</span>
              <span className={`status-badge ${purchase.receipt_status === 'Ordered' ? 'status-warning' : 'status-ok'}`}>{purchase.receipt_status}</span>
            </div>
          </div>
        </div>
      </Card>

      {isPrivileged && (
        <DocumentsPanel title="Documents" api={{
          list: () => documentsAPI.list('purchase', purchaseId),
          upload: (file, description) => documentsAPI.upload('purchase', purchaseId, file, description),
          downloadUrl: (documentId) => documentsAPI.downloadUrl('purchase', purchaseId, documentId),
          remove: (documentId) => documentsAPI.remove('purchase', purchaseId, documentId),
        }} canUpload={isPrivileged} />
      )}
    </div>
  );
}

// --- PurchaseImportPage.jsx ---
function PurchaseImportPage() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [excludedRows, setExcludedRows] = useState({}); // row_number -> true if user opted out
  const [createDecisions, setCreateDecisions] = useState({}); // row_number -> bool, for new-material rows
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [downloadingErrors, setDownloadingErrors] = useState(false);

  const handleFileChange = (e) => {
    setFile(e.target.files[0] || null);
    setPreview(null);
    setResult(null);
    setError('');
  };

  const handlePreview = async () => {
    if (!file) return;
    setLoading(true);
    setError('');
    try {
      const res = await purchaseImportAPI.preview(file);
      setPreview(res.data);
      // Default: include every error-free row; default new materials to "create"
      const decisions = {};
      res.data.rows.forEach((r) => { if (r.is_new_material) decisions[r.row_number] = true; });
      setCreateDecisions(decisions);
      setExcludedRows({});
    } catch (err) {
      setError(err.response?.data?.detail || 'Could not read this file. Make sure you used the downloaded template.');
    } finally {
      setLoading(false);
    }
  };

  const handleCommit = async () => {
    if (!preview) return;
    setLoading(true);
    setError('');
    try {
      const rowsToCommit = preview.rows
        .filter((r) => r.errors.length === 0 && !excludedRows[r.row_number])
        .map((r) => ({
          material_name: r.material_name, specification: r.specification,
          matched_material_id: r.matched_material_id, matched_supplier_id: r.matched_supplier_id,
          quantity: r.quantity, unit: r.unit, rate: r.rate, gst_percent: r.gst_percent || '0',
          invoice_date: r.invoice_date, remarks: r.remarks,
          create_new_material: r.is_new_material ? !!createDecisions[r.row_number] : false,
        }))
        .filter((r) => r.matched_material_id || r.create_new_material);

      const res = await purchaseImportAPI.commit(rowsToCommit);
      setResult(res.data);
      setPreview(null);
      setFile(null);
    } catch (err) {
      setError(err.response?.data?.detail || 'Import failed');
    } finally {
      setLoading(false);
    }
  };

  const downloadErrorReport = async () => {
    if (!file) return;
    setDownloadingErrors(true);
    setError('');
    try {
      const res = await purchaseImportAPI.errorReport(file);
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'Woodful_Purchase_Import_Errors.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError('Could not generate the error report. Please try again.');
    } finally {
      setDownloadingErrors(false);
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Import Purchases from Excel</h1>
          <p className="page-summary">
            Download the template, fill in one row per material purchased, then upload it here for review
            before anything is saved.
          </p>
        </div>
      </div>

      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {result && (
        <Card>
          <div className="card-body">
            <h3 style={{ marginTop: 0 }}>Import Complete</h3>
            <p>
              {result.created_purchases} purchase{result.created_purchases !== 1 ? 's' : ''} created
              {result.created_materials > 0 && `, ${result.created_materials} new material${result.created_materials !== 1 ? 's' : ''} added`}.
            </p>
            {result.error && <Alert type="warning" message={result.error} />}
          </div>
        </Card>
      )}

      {!preview && (
        <Card>
          <div className="card-body">
            <p style={{ marginTop: 0 }}>
              <a href={purchaseImportAPI.templateUrl} className="btn-secondary" style={{ display: 'inline-block', textDecoration: 'none' }}>
                Download Template
              </a>
            </p>
            <div style={{ marginTop: 16 }}>
              <input type="file" accept=".xlsx" onChange={handleFileChange} />
            </div>
            <button className="btn-primary" style={{ marginTop: 16 }} onClick={handlePreview} disabled={!file || loading}>
              {loading ? 'Reading file...' : 'Preview Import'}
            </button>
          </div>
        </Card>
      )}

      {preview && (
        <>
          <Card>
            <div className="card-body">
              <h3 style={{ marginTop: 0 }}>{preview.total_rows} rows detected</h3>
              <p>
                {preview.matched_rows} matched existing material &middot; {preview.new_material_rows} new material{preview.new_material_rows !== 1 ? 's' : ''} detected &middot;{' '}
                {preview.error_rows} row{preview.error_rows !== 1 ? 's' : ''} with errors
                {preview.error_rows > 0 ? ' (won\'t be imported)' : ''}.
              </p>
              {preview.error_rows > 0 && (
                <button className="btn-link" onClick={downloadErrorReport} disabled={downloadingErrors}>
                  {downloadingErrors ? 'Preparing report...' : 'Download Error Report'}
                </button>
              )}
            </div>
          </Card>

          <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th></th><th>Material</th><th>Qty</th><th>Unit</th><th>Supplier</th>
                <th>Rate</th><th>Status</th>
              </tr>
            </thead>
            <tbody>
              {preview.rows.map((r) => (
                <tr key={r.row_number} style={{ opacity: excludedRows[r.row_number] ? 0.5 : 1 }}>
                  <td>
                    {r.errors.length === 0 && (
                      <input
                        type="checkbox" checked={!excludedRows[r.row_number]}
                        onChange={(e) => setExcludedRows((prev) => ({ ...prev, [r.row_number]: !e.target.checked }))}
                      />
                    )}
                  </td>
                  <td>{r.material_name}</td>
                  <td>{r.quantity != null ? Number(r.quantity) : '-'}</td>
                  <td>{r.unit}</td>
                  <td>{r.supplier_name}</td>
                  <td>{r.rate != null ? formatCurrency(r.rate) : '-'}</td>
                  <td>
                    {r.errors.length > 0 ? (
                      <span className="status-badge status-danger">{r.errors.join('; ')}</span>
                    ) : r.is_new_material ? (
                      <label style={{ fontSize: '0.8rem' }}>
                        <input
                          type="checkbox" checked={!!createDecisions[r.row_number]}
                          onChange={(e) => setCreateDecisions((prev) => ({ ...prev, [r.row_number]: e.target.checked }))}
                        />{' '}
                        New - Create Material
                      </label>
                    ) : (
                      <span className="status-badge status-ok">Matched</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>

          <div style={{ marginTop: 16, display: 'flex', gap: 12 }}>
            <button className="btn-primary" onClick={handleCommit} disabled={loading}>
              {loading ? 'Importing...' : 'Confirm Import'}
            </button>
            <button className="btn-secondary" onClick={() => { setPreview(null); setFile(null); }}>Cancel</button>
          </div>
        </>
      )}
    </div>
  );
}

export { SuppliersPage, SupplierDetailPage, PurchasesPage, PurchaseDetailPage, PurchaseImportPage };
