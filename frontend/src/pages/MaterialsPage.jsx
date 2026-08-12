import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { materialsAPI, suppliersAPI, reportsAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import KpiCard from '../components/common/KpiCard';
import Pagination from '../components/common/Pagination';
import { formatCurrency } from '../utils/currency';

const PAGE_SIZE = 25;

function MaterialsPage() {
  const navigate = useNavigate();
  const [materials, setMaterials] = useState([]);
  const [allMaterials, setAllMaterials] = useState([]); // unfiltered, for the summary metrics
  const [suppliers, setSuppliers] = useState([]);
  const [search, setSearch] = useState('');
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const location = useLocation();
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [editingMaterial, setEditingMaterial] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  const load = (params, pageNum = 1) => {
    const offset = (pageNum - 1) * PAGE_SIZE;
    setPageLoading(true);
    materialsAPI.list({ ...params, limit: PAGE_SIZE, offset }).then((res) => {
      setMaterials(res.data);
      setTotalCount(Number(res.headers['x-total-count'] || res.data.length));
    }).finally(() => setPageLoading(false));
    materialsAPI.list().then((res) => setAllMaterials(res.data));
    suppliersAPI.list().then((res) => setSuppliers(res.data));
  };

  useEffect(() => load(), []);

  const activeFilters = () => {
    const params = {};
    if (search) params.search = search;
    if (lowStockOnly) params.low_stock_only = true;
    return params;
  };

  const applyFilters = (e) => {
    e?.preventDefault();
    setPage(1);
    load(activeFilters(), 1);
  };

  const goToPage = (pageNum) => {
    setPage(pageNum);
    load(activeFilters(), pageNum);
  };

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await materialsAPI.create({
        ...formData,
        minimum_stock: Number(formData.minimum_stock || 0),
        opening_stock: Number(formData.opening_stock || 0),
        average_rate: formData.average_rate || '0',
        supplier_id: formData.supplier_id ? Number(formData.supplier_id) : null,
      });
      setShowAdd(false);
      applyFilters();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add material');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await materialsAPI.update(editingMaterial.id, {
        name: formData.name, category: formData.category, brand_grade: formData.brand_grade,
        thickness_size: formData.thickness_size, unit: formData.unit,
        minimum_stock: Number(formData.minimum_stock || 0), average_rate: formData.average_rate,
        supplier_id: formData.supplier_id ? Number(formData.supplier_id) : null, location: formData.location,
      });
      setEditingMaterial(null);
      applyFilters();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update material');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    { key: 'material_code', label: 'Material ID' }, { key: 'name', label: 'Name' },
    { key: 'category', label: 'Category' }, { key: 'unit', label: 'Unit' },
    { key: 'current_stock', label: 'Available Stock' }, { key: 'minimum_stock', label: 'Reorder Level' },
    { key: 'stock_status', label: 'Status' },
    { key: 'average_rate', label: 'Avg Rate', render: (v) => formatCurrency(v) },
    { key: 'stock_value', label: 'Stock Value', render: (v) => formatCurrency(v) },
    { key: 'location', label: 'Location' },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingMaterial(row); }}>Edit</button>
      ),
    },
  ];

  const createFields = [
    { name: 'name', label: 'Name', required: true },
    { name: 'category', label: 'Category' },
    { name: 'brand_grade', label: 'Brand/Grade' },
    { name: 'thickness_size', label: 'Thickness/Size' },
    { name: 'unit', label: 'Unit', required: true, placeholder: 'Sheets' },
    { name: 'opening_stock', label: 'Opening Stock', type: 'number' },
    { name: 'minimum_stock', label: 'Reorder Level', type: 'number' },
    { name: 'average_rate', label: 'Average Rate', type: 'number' },
    { name: 'supplier_id', label: 'Primary Supplier', type: 'select', options: suppliers.map((s) => ({ value: s.id, label: s.name })) },
    { name: 'location', label: 'Location' },
  ];

  const editFields = createFields.filter((f) => !['material_code', 'opening_stock'].includes(f.name));

  const inventoryValue = allMaterials.reduce((sum, m) => sum + (m.stock_value || 0), 0);
  const lowStockCount = allMaterials.filter((m) => m.stock_status === 'LOW STOCK').length;
  const outOfStockCount = allMaterials.filter((m) => m.stock_status === 'OUT OF STOCK').length;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Materials</h1>
          <p className="page-summary">Track live stock, purchases, and issues across every material.</p>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('stock-dashboard.xlsx')} target="_blank" rel="noreferrer">
            Export Stock Dashboard
          </a>
          <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Material</button>
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}
      <div className="kpi-row">
        <KpiCard label="Inventory Value" value={formatCurrency(inventoryValue)} />
        <KpiCard label="Low Stock" value={lowStockCount} tone={lowStockCount > 0 ? 'warning' : 'success'} />
        <KpiCard label="Out of Stock" value={outOfStockCount} tone={outOfStockCount > 0 ? 'danger' : 'success'} />
      </div>
      <form className="page-search" onSubmit={applyFilters}>
        <input
          type="text" placeholder="Search by name or code..." value={search}
          onChange={(e) => setSearch(e.target.value)} className="form-input"
        />
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.85rem', whiteSpace: 'nowrap' }}>
          <input type="checkbox" checked={lowStockOnly} onChange={(e) => setLowStockOnly(e.target.checked)} />
          Low stock only
        </label>
        <button type="submit" className="btn-secondary">Filter</button>
      </form>
      <Table columns={columns} data={materials} loading={pageLoading} onRowClick={(row) => navigate(`/materials/${row.id}`)} emptyMessage="No materials yet. Add your first material to begin tracking inventory." />
      {totalCount > PAGE_SIZE && (
        <Pagination
          currentPage={page}
          totalPages={Math.ceil(totalCount / PAGE_SIZE)}
          onPageChange={goToPage}
        />
      )}

      <Modal isOpen={showAdd} title="Add Material" onClose={() => setShowAdd(false)}>
        <Form fields={createFields} onSubmit={handleCreate} loading={loading} submitText="Add Material" />
      </Modal>
      <Modal isOpen={!!editingMaterial} title={`Edit ${editingMaterial?.name || ''}`} onClose={() => setEditingMaterial(null)}>
        {editingMaterial && (
          <Form fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes" initialValues={editingMaterial} />
        )}
      </Modal>
    </div>
  );
}

export default MaterialsPage;
