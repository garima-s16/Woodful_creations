import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { purchasesAPI, suppliersAPI, materialsAPI, reportsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import { formatCurrency } from '../utils/currency';
import { today } from '../utils/dates';

function PurchasesPage() {
  const navigate = useNavigate();
  const [purchases, setPurchases] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [materials, setMaterials] = useState([]);
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);

  const load = () => {
    setPageLoading(true);
    purchasesAPI.list().then((res) => setPurchases(res.data)).finally(() => setPageLoading(false));
    suppliersAPI.list().then((res) => setSuppliers(res.data));
    materialsAPI.list().then((res) => setMaterials(res.data));
  };
  useEffect(load, []);

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await purchasesAPI.create({
        ...formData,
        supplier_id: Number(formData.supplier_id),
        material_id: Number(formData.material_id),
        quantity: formData.quantity, rate: formData.rate,
        gst_percent: formData.gst_percent || '18',
        date: new Date(formData.date).toISOString(),
      });
      setShowAdd(false);
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to record purchase');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'purchase_code', label: 'Purchase ID' },
    { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
    { key: 'supplier_id', label: 'Supplier', render: (v) => suppliers.find((s) => s.id === v)?.name || v },
    { key: 'material_id', label: 'Material', render: (v) => materials.find((m) => m.id === v)?.name || v },
    { key: 'quantity', label: 'Quantity' }, { key: 'unit', label: 'Unit' }, { key: 'rate', label: 'Rate' },
    { key: 'invoice_total', label: 'Invoice Total', render: (v) => formatCurrency(v) },
    { key: 'payment_status', label: 'Payment Status' },
  ];

  const fields = [
    { name: 'supplier_id', label: 'Supplier', type: 'select', required: true, section: 'Supplier & Invoice', options: suppliers.map((s) => ({ value: s.id, label: s.name })) },
    { name: 'date', label: 'Date', type: 'date', required: true, section: 'Supplier & Invoice' },
    { name: 'material_id', label: 'Material', type: 'select', required: true, section: 'Material', options: materials.map((m) => ({ value: m.id, label: m.name })) },
    { name: 'quantity', label: 'Quantity', type: 'number', required: true, section: 'Quantity & Cost' },
    { name: 'unit', label: 'Unit', required: true, placeholder: 'Sheets', section: 'Quantity & Cost' },
    { name: 'rate', label: 'Rate', type: 'number', required: true, section: 'Quantity & Cost' },
    { name: 'gst_percent', label: 'GST %', type: 'number', placeholder: '18', section: 'Tax' },
    { name: 'payment_status', label: 'Payment Status', type: 'select', section: 'Payment', options: [
      { value: 'Paid', label: 'Paid' }, { value: 'Part Paid', label: 'Part Paid' }, { value: 'Credit', label: 'Credit' },
    ] },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>Purchases (Stock In)</h1>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('purchases.xlsx')} target="_blank" rel="noreferrer">Export</a>
          <button className="btn-primary" onClick={() => setShowAdd(true)}>Record Purchase</button>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <Table columns={columns} data={purchases} loading={pageLoading} onRowClick={(row) => navigate(`/purchases/${row.id}`)} emptyMessage="No purchases recorded yet. Record your first purchase to start tracking inventory." />
      <Modal isOpen={showAdd} title="Record Purchase" onClose={() => setShowAdd(false)}>
        <Form fields={fields} onSubmit={handleCreate} loading={loading} submitText="Record Purchase"
          initialValues={{ date: today() }} />
      </Modal>
    </div>
  );
}

export default PurchasesPage;
