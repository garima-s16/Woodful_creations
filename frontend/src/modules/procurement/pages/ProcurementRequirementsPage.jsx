import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { procurementRequirementsAPI, ordersAPI, materialsAPI } from '../../../utils/api';
import Table from '../../../components/common/Table';
import Modal from '../../../components/common/Modal';
import Form from '../../../components/common/Form';
import Alert from '../../../components/common/Alert';
import { statusClass } from '../../../utils/format';

function ProcurementRequirementsPage() {
  const navigate = useNavigate();
  const [requirements, setRequirements] = useState([]);
  const [orders, setOrders] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = () => {
    setPageLoading(true);
    setLoadError(false);
    procurementRequirementsAPI.list().then((res) => setRequirements(res.data)).catch((err) => {
      setLoadError(true);
      setError(err.response?.status === 403 ? 'You do not have permission to view procurement requirements.' : 'Unable to load procurement requirements. Please try again.');
    }).finally(() => setPageLoading(false));
    ordersAPI.list().then((res) => setOrders(res.data)).catch(() => setOrders([]));
    materialsAPI.list().then((res) => setMaterials(res.data)).catch(() => setMaterials([]));
  };
  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await procurementRequirementsAPI.create({
        ...formData, order_id: Number(formData.order_id), material_id: Number(formData.material_id),
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create the procurement requirement - the order may already have this material fully available.');
    } finally {
      setLoading(false);
    }
  };

  const fields = [
    { name: 'order_id', label: 'Order', type: 'select', required: true, options: orders.map((o) => ({ value: o.id, label: o.order_code })) },
    { name: 'material_id', label: 'Material', type: 'select', required: true, options: materials.map((m) => ({ value: m.id, label: m.name })) },
    { name: 'priority', label: 'Priority', type: 'select', options: [
      { value: 'High', label: 'High' }, { value: 'Medium', label: 'Medium' }, { value: 'Low', label: 'Low' },
    ] },
    { name: 'required_by_date', label: 'Required By', type: 'date' },
    { name: 'remarks', label: 'Remarks', type: 'textarea' },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Procurement Requirements</h1>
        <button className="btn btn-primary" onClick={() => setShowAdd(true)}>Snapshot Shortage as Requirement</button>
      </div>
      {error && <Alert type="error" message={error} />}
      <Table
        columns={[
          { key: 'material_name', label: 'Material' },
          { key: 'required_quantity', label: 'Required' },
          { key: 'available_quantity_at_creation', label: 'Available (at creation)' },
          { key: 'shortage_quantity_at_creation', label: 'Shortage (at creation)' },
          { key: 'priority', label: 'Priority' },
          { key: 'status', label: 'Status', render: (v) => <span className={statusClass(v)}>{v}</span> },
        ]}
        data={loadError ? [] : requirements}
        error={loadError}
        onRetry={load}
        loading={pageLoading}
        onRowClick={(row) => navigate(`/procurement-requirements/${row.id}`)}
        emptyMessage="No procurement requirements yet. Create one from an order's material shortage."
      />
      <Modal isOpen={showAdd} title="Snapshot Shortage as Requirement" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Create Requirement" />
      </Modal>
    </div>
  );
}

export default ProcurementRequirementsPage;
