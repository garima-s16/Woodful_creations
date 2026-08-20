import React, { useEffect, useState } from 'react';
import { useSelector } from 'react-redux';
import { issuesAPI, materialsAPI, ordersAPI, reportsAPI, locationsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';

function IssuesPage() {
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [issues, setIssues] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [orders, setOrders] = useState([]);
  const [locations, setLocations] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);

  const load = () => {
    setPageLoading(true);
    issuesAPI.list().then((res) => setIssues(res.data)).catch(() => {}).finally(() => setPageLoading(false));
    materialsAPI.list().then((res) => setMaterials(res.data)).catch(() => {});
    ordersAPI.list().then((res) => setOrders(res.data)).catch(() => {});
    locationsAPI.list().then((res) => setLocations(res.data)).catch(() => setLocations([]));
  };
  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await issuesAPI.create({
        ...formData,
        material_id: Number(formData.material_id),
        order_id: formData.order_id ? Number(formData.order_id) : null,
        location_id: formData.location_id ? Number(formData.location_id) : null,
        date: new Date(formData.date).toISOString(),
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to record issue');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'issue_code', label: 'Issue ID' },
    { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
    { key: 'order_id', label: 'Order', render: (v) => orders.find((o) => o.id === v)?.order_code || '-' },
    { key: 'material_id', label: 'Material', render: (v) => materials.find((m) => m.id === v)?.name || v },
    { key: 'quantity_issued', label: 'Quantity' }, { key: 'unit', label: 'Unit' },
    { key: 'issued_to', label: 'Issued To' }, { key: 'department', label: 'Department' },
  ];

  const fields = [
    { name: 'date', label: 'Date', type: 'date', required: true },
    { name: 'material_id', label: 'Material', type: 'select', required: true, options: materials.map((m) => ({ value: m.id, label: `${m.name} (${m.current_stock} in stock)` })) },
    { name: 'order_id', label: 'Order (Project)', type: 'select', options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'quantity_issued', label: 'Quantity Issued', type: 'number', required: true },
    { name: 'unit', label: 'Unit', required: true, placeholder: 'Sheets' },
    { name: 'location_id', label: 'Issue From Location', type: 'select', options: locations.map((l) => ({ value: l.id, label: l.full_path })), placeholder: 'Primary location' },
    { name: 'issued_to', label: 'Issued To' },
    { name: 'department', label: 'Department' },
    { name: 'purpose', label: 'Purpose' },
    { name: 'approved_by', label: 'Approved By' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Issues (Stock Out)</h1>
          <p className="page-summary">Record materials issued from stock for production and project use.</p>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('issues.xlsx')} target="_blank" rel="noreferrer">Export</a>
          {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Record Issue</button>}
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={issues} loading={pageLoading} emptyMessage="No materials issued yet. Issued materials will appear here." />
      <Modal isOpen={showAdd} title="Record Issue" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Record Issue" />
      </Modal>
    </div>
  );
}

export default IssuesPage;
