import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { productsAPI, productCategoriesAPI, materialsAPI, productImportAPI } from '../utils/api';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import ConfirmDialog from '../components/common/ConfirmDialog';
import Form from '../components/common/Form';
import Alert from '../components/common/Alert';
import KpiCard from '../components/common/KpiCard';
import Pagination from '../components/common/Pagination';
import { GridIcon, ListIcon, SlidersIcon, SearchIcon, CartIcon } from '../components/icons';
import { formatCurrency } from '../utils/currency';
import '../styles/components/MaterialCatalog.css';
import '../styles/components/ProductCatalog.css';

const PAGE_SIZE = 24;
const DIMENSION_UNITS = [
  { value: 'in', label: 'inches' }, { value: 'cm', label: 'cm' },
  { value: 'ft', label: 'feet' }, { value: 'mm', label: 'mm' },
];

const emptyBomRow = () => ({ material_id: '', quantity: '1', unit: '' });

function BomEditor({ items, onChange, materials }) {
  const updateRow = (idx, field, value) => onChange(items.map((r, i) => (i === idx ? { ...r, [field]: value } : r)));
  const addRow = () => onChange([...items, emptyBomRow()]);
  const removeRow = (idx) => onChange(items.filter((_, i) => i !== idx));
  return (
    <div className="product-bom-editor">
      <label className="form-label" style={{ display: 'block', marginBottom: 6 }}>Bill of Materials (optional)</label>
      {items.map((row, idx) => (
        <div className="product-bom-row" key={idx}>
          <select value={row.material_id} onChange={(e) => updateRow(idx, 'material_id', e.target.value)}>
            <option value="">Select material...</option>
            {materials.map((m) => <option key={m.id} value={m.id}>{m.name}</option>)}
          </select>
          <input type="number" min="0" step="0.01" placeholder="Qty" value={row.quantity}
                 onChange={(e) => updateRow(idx, 'quantity', e.target.value)} />
          <input type="text" placeholder="Unit" value={row.unit}
                 onChange={(e) => updateRow(idx, 'unit', e.target.value)} />
          <button type="button" className="line-item-remove" onClick={() => removeRow(idx)} title="Remove">×</button>
        </div>
      ))}
      <button type="button" className="btn-secondary btn-small product-bom-add" onClick={addRow}>+ Add Material</button>
    </div>
  );
}

function ProductsPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';

  const [products, setProducts] = useState([]);
  const [allProducts, setAllProducts] = useState([]);
  const [categories, setCategories] = useState([]);
  const [materials, setMaterials] = useState([]);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');
  const [activeOnly, setActiveOnly] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [filterCategoryId, setFilterCategoryId] = useState('');
  const [filterSubcategoryId, setFilterSubcategoryId] = useState('');
  const [view, setView] = useState('grid');
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const [pageLoading, setPageLoading] = useState(true);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [editingProduct, setEditingProduct] = useState(null);
  const [pendingDelete, setPendingDelete] = useState(null);
  const [bomItems, setBomItems] = useState([]);
  const [formCategoryId, setFormCategoryId] = useState('');
  const [formSubcategoryId, setFormSubcategoryId] = useState('');

  const [showCategoryAdmin, setShowCategoryAdmin] = useState(false);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [newSubcategoryName, setNewSubcategoryName] = useState('');
  const [newSubcategoryParent, setNewSubcategoryParent] = useState('');

  const [showImport, setShowImport] = useState(false);
  const [importFile, setImportFile] = useState(null);
  const [importPreview, setImportPreview] = useState(null);
  const [importResult, setImportResult] = useState(null);
  const [importBusy, setImportBusy] = useState(false);

  const load = (params = {}, pageNum = 1) => {
    const offset = (pageNum - 1) * PAGE_SIZE;
    setPageLoading(true);
    setError('');
    productsAPI.list({ ...params, limit: PAGE_SIZE, offset }).then((res) => {
      setProducts(res.data);
      setTotalCount(Number(res.headers['x-total-count'] || res.data.length));
    }).catch(() => {
      setProducts([]);
      setTotalCount(0);
      setError('Could not load products. Check that the backend server is running and reachable.');
    }).finally(() => setPageLoading(false));
    productsAPI.list().then((res) => setAllProducts(res.data)).catch(() => setAllProducts([]));
    productCategoriesAPI.list().then((res) => setCategories(res.data)).catch(() => setCategories([]));
    materialsAPI.list().then((res) => setMaterials(res.data)).catch(() => setMaterials([]));
  };

  useEffect(() => load(), []); // eslint-disable-line react-hooks/exhaustive-deps

  const serverFilters = () => {
    const params = {};
    if (search) params.search = search;
    if (typeFilter) params.product_type = typeFilter;
    if (activeOnly) params.active_only = true;
    if (filterSubcategoryId) params.subcategory_id = filterSubcategoryId;
    return params;
  };

  const applyFilters = (e) => {
    e?.preventDefault();
    setPage(1);
    load(serverFilters(), 1);
  };

  const goToPage = (pageNum) => {
    setPage(pageNum);
    load(serverFilters(), pageNum);
  };

  const clearFilters = () => {
    setSearch(''); setTypeFilter(''); setActiveOnly(false);
    setFilterCategoryId(''); setFilterSubcategoryId('');
    setPage(1); load({}, 1);
  };

  const resetFormState = () => {
    setBomItems([]);
    setFormCategoryId('');
    setFormSubcategoryId('');
  };

  const handleCreate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await productsAPI.create({
        ...formData,
        subcategory_id: formSubcategoryId ? Number(formSubcategoryId) : null,
        length: formData.length || null, width: formData.width || null, height: formData.height || null,
        lead_time_days: formData.lead_time_days ? Number(formData.lead_time_days) : null,
        cost_price: formData.cost_price || '0', selling_price: formData.selling_price || '0',
        tax_percent: formData.tax_percent || '18',
        bom_items: bomItems.filter((b) => b.material_id).map((b) => ({
          material_id: Number(b.material_id), quantity: b.quantity || '1', unit: b.unit || null,
        })),
      });
      setShowAdd(false);
      resetFormState();
      applyFilters();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create product');
    } finally {
      setLoading(false);
    }
  };

  const handleUpdate = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await productsAPI.update(editingProduct.id, {
        ...formData,
        is_active: formData.is_active === 'true' || formData.is_active === true,
        subcategory_id: formSubcategoryId ? Number(formSubcategoryId) : null,
        length: formData.length || null, width: formData.width || null, height: formData.height || null,
        lead_time_days: formData.lead_time_days ? Number(formData.lead_time_days) : null,
        bom_items: bomItems.filter((b) => b.material_id).map((b) => ({
          material_id: Number(b.material_id), quantity: b.quantity || '1', unit: b.unit || null,
        })),
      });
      setEditingProduct(null);
      resetFormState();
      applyFilters();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update product');
    } finally {
      setLoading(false);
    }
  };

  const openEdit = (product) => {
    setEditingProduct(product);
    setBomItems((product.bom_items || []).map((b) => ({ material_id: String(b.material_id), quantity: String(b.quantity), unit: b.unit || '' })));
    const sub = categories.flatMap((c) => c.subcategories).find((s) => s.id === product.subcategory_id);
    setFormSubcategoryId(product.subcategory_id ? String(product.subcategory_id) : '');
    setFormCategoryId(sub ? String(sub.category_id) : '');
  };

  // Supports deep-linking into the edit modal from ProductDetailPage's
  // "Manage in Product Master" button, which navigates here with
  // { state: { openEditId } }. Waits for both allProducts and categories
  // to be loaded (openEdit needs categories to resolve the subcategory's
  // parent category), then opens the matching product exactly once.
  useEffect(() => {
    if (!location.state?.openEditId || allProducts.length === 0 || categories.length === 0) return;
    const product = allProducts.find((p) => p.id === location.state.openEditId);
    if (product) openEdit(product);
    navigate(location.pathname, { replace: true, state: {} });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allProducts, categories, location.state]);

  const confirmDelete = async () => {
    setError('');
    try {
      await productsAPI.remove(pendingDelete.id);
      setPendingDelete(null);
      applyFilters();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete product');
      setPendingDelete(null);
    }
  };

  const handleCreateCategory = async (e) => {
    e.preventDefault();
    if (!newCategoryName.trim()) return;
    try {
      await productCategoriesAPI.createCategory({ name: newCategoryName.trim() });
      setNewCategoryName('');
      productCategoriesAPI.list().then((res) => setCategories(res.data));
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create category');
    }
  };

  const handleCreateSubcategory = async (e) => {
    e.preventDefault();
    if (!newSubcategoryName.trim() || !newSubcategoryParent) return;
    try {
      await productCategoriesAPI.createSubcategory({ category_id: Number(newSubcategoryParent), name: newSubcategoryName.trim() });
      setNewSubcategoryName('');
      productCategoriesAPI.list().then((res) => setCategories(res.data));
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create subcategory');
    }
  };

  const handleImportFile = (e) => {
    setImportFile(e.target.files[0] || null);
    setImportPreview(null);
    setImportResult(null);
  };

  const runImportPreview = async () => {
    if (!importFile) return;
    setImportBusy(true);
    setError('');
    try {
      const res = await productImportAPI.preview(importFile);
      setImportPreview(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to validate the uploaded file');
    } finally {
      setImportBusy(false);
    }
  };

  const runImportCommit = async () => {
    if (!importPreview) return;
    setImportBusy(true);
    setError('');
    try {
      const validRows = importPreview.rows.filter((r) => r.errors.length === 0).map((r) => ({
        name: r.name, sku: r.sku || null, product_type: r.product_type,
        subcategory_id: r.subcategory_id, description: r.description,
        length: r.length, width: r.width, height: r.height, dimension_unit: r.dimension_unit || 'in',
        finish: r.finish, unit: r.unit || 'Piece',
        cost_price: r.cost_price || '0', selling_price: r.selling_price || '0', tax_percent: r.tax_percent || '18',
        lead_time_days: r.lead_time_days, notes: r.notes,
      }));
      const res = await productImportAPI.commit(validRows);
      setImportResult(res.data);
      applyFilters();
    } catch (err) {
      setError(err.response?.data?.detail || 'Import failed');
    } finally {
      setImportBusy(false);
    }
  };

  const closeImport = () => {
    setShowImport(false);
    setImportFile(null);
    setImportPreview(null);
    setImportResult(null);
  };

  const subcategoryOptionsFor = (categoryId) => {
    const cat = categories.find((c) => String(c.id) === String(categoryId));
    return cat?.subcategories || [];
  };

  const createFields = useMemo(() => ([
    { name: 'name', label: 'Product Name', required: true, section: 'Identity' },
    { name: 'sku', label: 'SKU (optional for custom products)', section: 'Identity' },
    { name: 'product_type', label: 'Type', type: 'select', required: true, section: 'Identity',
      options: [{ value: 'standard', label: 'Standard (catalog)' }, { value: 'custom', label: 'Custom (one-off)' }] },
    { name: 'unit', label: 'Unit', placeholder: 'Piece', section: 'Identity' },

    { name: 'description', label: 'Description', type: 'textarea', section: 'Details' },
    { name: 'specifications', label: 'Specifications', type: 'textarea', section: 'Details' },
    { name: 'finish', label: 'Finish', placeholder: 'e.g. White Laminate', section: 'Details' },
    { name: 'notes', label: 'Notes', type: 'textarea', section: 'Details' },

    { name: 'length', label: 'Length', type: 'number', section: 'Dimensions' },
    { name: 'width', label: 'Width', type: 'number', section: 'Dimensions' },
    { name: 'height', label: 'Height', type: 'number', section: 'Dimensions' },
    { name: 'dimension_unit', label: 'Dimension Unit', type: 'select', section: 'Dimensions', options: DIMENSION_UNITS },

    { name: 'cost_price', label: 'Cost Price', type: 'number', section: 'Costing' },
    { name: 'selling_price', label: 'Selling Price', type: 'number', section: 'Costing' },
    { name: 'tax_percent', label: 'Tax % (GST)', type: 'number', placeholder: '18', section: 'Costing' },
    { name: 'lead_time_days', label: 'Lead Time (days)', type: 'number', section: 'Costing' },
  ]), []);

  const editFields = createFields.map(({ section, ...rest }) => rest).concat([
    { name: 'is_active', label: 'Active', type: 'select', options: [{ value: 'true', label: 'Active' }, { value: 'false', label: 'Inactive' }] },
  ]);

  const columns = [
    { key: 'product_code', label: 'Product ID' }, { key: 'name', label: 'Name' },
    { key: 'sku', label: 'SKU', render: (v) => v || '-' },
    { key: 'product_type', label: 'Type', render: (v) => v === 'custom' ? 'Custom' : 'Standard' },
    { key: 'category', label: 'Category', render: (v) => v || '-' },
    { key: 'selling_price', label: 'Selling Price', render: formatCurrency },
    { key: 'cost_price', label: 'Cost Price', render: (v) => v != null ? formatCurrency(v) : 'Restricted' },
    { key: 'is_active', label: 'Status', render: (v) => <span className={`status-badge ${v ? 'status-ok' : 'status-muted'}`}>{v ? 'Active' : 'Inactive'}</span> },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        isPrivileged ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); openEdit(row); }}>Edit</button> : null
      ),
    },
    {
      key: 'delete_action', label: '', render: (v, row) => (
        isPrivileged ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); setPendingDelete(row); }}>Delete</button> : null
      ),
    },
  ];

  const standardCount = allProducts.filter((p) => p.product_type === 'standard').length;
  const customCount = allProducts.filter((p) => p.product_type === 'custom').length;
  const activeCount = allProducts.filter((p) => p.is_active).length;
  const hasAnyProducts = allProducts.length > 0;
  const activeFilterCount = [typeFilter, activeOnly, filterSubcategoryId].filter(Boolean).length;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Product Master</h1>
          <p className="page-summary">The real catalog of what Woodful sells and builds - standard products and custom furniture, one system of record.</p>
        </div>
        {isPrivileged && (
          <div className="page-actions">
            <button className="btn-secondary" onClick={() => setShowCategoryAdmin(true)}>Manage Categories</button>
            <a className="btn-secondary" href={productImportAPI.templateUrl}>Download Import Template</a>
            <button className="btn-secondary" onClick={() => setShowImport(true)}>Bulk Import</button>
            <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Product</button>
          </div>
        )}
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <div className="kpi-row">
        <KpiCard label="Total Products" value={allProducts.length} />
        <KpiCard label="Standard" value={standardCount} />
        <KpiCard label="Custom" value={customCount} />
        <KpiCard label="Active" value={activeCount} tone="success" />
      </div>

      {hasAnyProducts && (
        <>
          <div className="catalog-toolbar">
            <form className="catalog-search" onSubmit={applyFilters}>
              <SearchIcon width={16} height={16} />
              <input type="text" placeholder="Search products by name, SKU, or code..." value={search}
                     onChange={(e) => setSearch(e.target.value)} />
              <button type="submit" className="btn-secondary catalog-search-btn">Search</button>
            </form>
            <button className={`btn-secondary catalog-filter-toggle ${activeFilterCount ? 'has-active' : ''}`} onClick={() => setShowFilters((v) => !v)}>
              <SlidersIcon width={15} height={15} /> Filters {activeFilterCount > 0 && <span className="filter-count">{activeFilterCount}</span>}
            </button>
            <div className="view-toggle">
              <button className={view === 'grid' ? 'active' : ''} onClick={() => setView('grid')} title="Grid view"><GridIcon width={16} height={16} /></button>
              <button className={view === 'list' ? 'active' : ''} onClick={() => setView('list')} title="List view"><ListIcon width={16} height={16} /></button>
              <button className={view === 'table' ? 'active' : ''} onClick={() => setView('table')} title="Table view">Table</button>
            </div>
          </div>

          {showFilters && (
            <div className="catalog-filter-panel">
              <label className="catalog-filter-field">
                Type
                <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
                  <option value="">All types</option>
                  <option value="standard">Standard</option>
                  <option value="custom">Custom</option>
                </select>
              </label>
              <label className="catalog-filter-field">
                Category
                <select value={filterCategoryId} onChange={(e) => { setFilterCategoryId(e.target.value); setFilterSubcategoryId(''); }}>
                  <option value="">All categories</option>
                  {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </label>
              {filterCategoryId && (
                <label className="catalog-filter-field">
                  Subcategory
                  <select value={filterSubcategoryId} onChange={(e) => setFilterSubcategoryId(e.target.value)}>
                    <option value="">All subcategories</option>
                    {subcategoryOptionsFor(filterCategoryId).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </label>
              )}
              <label className="catalog-filter-field catalog-filter-checkbox">
                <input type="checkbox" checked={activeOnly} onChange={(e) => setActiveOnly(e.target.checked)} />
                Active only
              </label>
              <button className="btn-secondary" onClick={applyFilters}>Apply</button>
              <button className="btn-link" onClick={clearFilters}>Clear all</button>
            </div>
          )}
        </>
      )}

      {!hasAnyProducts && !pageLoading ? (
        <div className="catalog-empty-state">
          <div className="catalog-empty-icon"><CartIcon width={28} height={28} /></div>
          <h3>No products in the catalog yet</h3>
          <p>Add your first product, or bulk-import a spreadsheet, to start building Woodful's product master.</p>
          {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Product</button>}
        </div>
      ) : view === 'table' ? (
        <>
          <Table columns={columns} data={products} loading={pageLoading} onRowClick={(row) => navigate(`/products/${row.id}`)} emptyMessage="No products match your filters." />
          {totalCount > PAGE_SIZE && <Pagination currentPage={page} totalPages={Math.ceil(totalCount / PAGE_SIZE)} onPageChange={goToPage} />}
        </>
      ) : pageLoading ? (
        <div className={view === 'grid' ? 'product-grid' : 'product-list'}>
          {Array.from({ length: 8 }).map((_, i) => <div key={i} className="material-card-skeleton" />)}
        </div>
      ) : products.length === 0 ? (
        <div className="catalog-empty-state">
          <h3>No products match your filters</h3>
          <p>Try a different search term, or clear filters to see the full catalog.</p>
          <button className="btn-secondary" onClick={clearFilters}>Clear filters</button>
        </div>
      ) : view === 'grid' ? (
        <>
          <div className="product-grid">
            {products.map((p) => (
              <div key={p.id} className={`product-card ${!p.is_active ? 'product-card-inactive' : ''}`} onClick={() => navigate(`/products/${p.id}`)}>
                <div className="product-card-media">
                  <CartIcon width={30} height={30} />
                </div>
                <div className="product-card-top">
                  <div>
                    <div className="product-card-name">{p.name}</div>
                    <div className="product-card-meta">{p.product_code} {p.category ? `· ${p.category}` : ''}</div>
                  </div>
                  <span className={`product-card-type-badge ${p.product_type}`}>{p.product_type}</span>
                </div>
                <div className="product-card-price-row">
                  <span className="product-card-price">{formatCurrency(p.selling_price)}</span>
                  {!p.is_active && <span className="status-badge status-muted">Inactive</span>}
                </div>
              </div>
            ))}
          </div>
          {totalCount > PAGE_SIZE && <Pagination currentPage={page} totalPages={Math.ceil(totalCount / PAGE_SIZE)} onPageChange={goToPage} />}
        </>
      ) : (
        <>
          <div className="product-list">
            {products.map((p) => (
              <div key={p.id} className="product-row-card" onClick={() => navigate(`/products/${p.id}`)}>
                <span className="product-row-name">{p.name}</span>
                <span className="product-row-meta">{p.product_code} {p.category ? `· ${p.category}` : ''} · {p.product_type}</span>
                <span className="product-row-price">{formatCurrency(p.selling_price)}</span>
              </div>
            ))}
          </div>
          {totalCount > PAGE_SIZE && <Pagination currentPage={page} totalPages={Math.ceil(totalCount / PAGE_SIZE)} onPageChange={goToPage} />}
        </>
      )}

      <Modal isOpen={showAdd} title="Add Product" onClose={() => { setShowAdd(false); resetFormState(); }}>
        <label className="catalog-filter-field" style={{ marginBottom: 8, display: 'block' }}>
          Category
          <select value={formCategoryId} onChange={(e) => { setFormCategoryId(e.target.value); setFormSubcategoryId(''); }}>
            <option value="">No category</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
        {formCategoryId && (
          <label className="catalog-filter-field" style={{ marginBottom: 8, display: 'block' }}>
            Subcategory
            <select value={formSubcategoryId} onChange={(e) => setFormSubcategoryId(e.target.value)}>
              <option value="">No subcategory</option>
              {subcategoryOptionsFor(formCategoryId).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select>
          </label>
        )}
        <BomEditor items={bomItems} onChange={setBomItems} materials={materials} />
        <Form fields={createFields} onSubmit={handleCreate} loading={loading} submitText="Add Product" />
      </Modal>

      <Modal isOpen={!!editingProduct} title={`Edit ${editingProduct?.name || ''}`} onClose={() => { setEditingProduct(null); resetFormState(); }}>
        {editingProduct && (
          <>
            <label className="catalog-filter-field" style={{ marginBottom: 8, display: 'block' }}>
              Category
              <select value={formCategoryId} onChange={(e) => { setFormCategoryId(e.target.value); setFormSubcategoryId(''); }}>
                <option value="">No category</option>
                {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
            {formCategoryId && (
              <label className="catalog-filter-field" style={{ marginBottom: 8, display: 'block' }}>
                Subcategory
                <select value={formSubcategoryId} onChange={(e) => setFormSubcategoryId(e.target.value)}>
                  <option value="">No subcategory</option>
                  {subcategoryOptionsFor(formCategoryId).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </label>
            )}
            <BomEditor items={bomItems} onChange={setBomItems} materials={materials} />
            <Form
              fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes"
              initialValues={{ ...editingProduct, is_active: String(editingProduct.is_active) }}
            />
          </>
        )}
      </Modal>

      <Modal isOpen={showCategoryAdmin} title="Manage Product Categories" onClose={() => setShowCategoryAdmin(false)}>
        <form onSubmit={handleCreateCategory} style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          <input type="text" placeholder="New category name" value={newCategoryName} onChange={(e) => setNewCategoryName(e.target.value)} style={{ flex: 1 }} />
          <button type="submit" className="btn-secondary">Add Category</button>
        </form>
        <form onSubmit={handleCreateSubcategory} style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          <select value={newSubcategoryParent} onChange={(e) => setNewSubcategoryParent(e.target.value)}>
            <option value="">Select category...</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <input type="text" placeholder="New subcategory name" value={newSubcategoryName} onChange={(e) => setNewSubcategoryName(e.target.value)} style={{ flex: 1 }} />
          <button type="submit" className="btn-secondary">Add Subcategory</button>
        </form>
        <div>
          {categories.map((c) => (
            <div key={c.id} style={{ marginBottom: 10 }}>
              <strong>{c.name}</strong>
              <div className="text-muted">{(c.subcategories || []).map((s) => s.name).join(', ') || 'No subcategories yet'}</div>
            </div>
          ))}
        </div>
      </Modal>

      <Modal isOpen={showImport} title="Bulk Import Products" onClose={closeImport}>
        <p className="text-muted" style={{ marginTop: 0 }}>
          Download the template, fill in one row per product (Category/Subcategory must already exist), then upload it here to preview before importing.
        </p>
        <a className="btn-secondary" href={productImportAPI.templateUrl} style={{ display: 'inline-block', marginBottom: 12 }}>Download Template</a>
        <div style={{ marginBottom: 12 }}>
          <input type="file" accept=".xlsx" onChange={handleImportFile} />
          <button className="btn-secondary" style={{ marginLeft: 8 }} disabled={!importFile || importBusy} onClick={runImportPreview}>
            {importBusy ? 'Validating...' : 'Validate & Preview'}
          </button>
        </div>
        {importPreview && (
          <>
            <p>
              {importPreview.total_rows} rows found - {importPreview.valid_rows} valid, {importPreview.error_rows} with errors.
            </p>
            <div style={{ maxHeight: 240, overflowY: 'auto', marginBottom: 12 }}>
              <table className="data-table">
                <thead><tr><th>Row</th><th>Name</th><th>Type</th><th>Category</th><th>Errors</th></tr></thead>
                <tbody>
                  {importPreview.rows.map((r) => (
                    <tr key={r.row_number} style={r.errors.length ? { color: 'var(--danger)' } : undefined}>
                      <td>{r.row_number}</td><td>{r.name}</td><td>{r.product_type}</td><td>{r.category_name || '-'}</td>
                      <td>{r.errors.join('; ')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <button className="btn-primary" disabled={importBusy || importPreview.valid_rows === 0} onClick={runImportCommit}>
              {importBusy ? 'Importing...' : `Import ${importPreview.valid_rows} Valid Row(s)`}
            </button>
          </>
        )}
        {importResult && (
          <Alert
            type={importResult.error ? 'warning' : 'success'}
            message={importResult.error
              ? `Created ${importResult.created_products} product(s). ${importResult.error}`
              : `Successfully imported ${importResult.created_products} product(s).`}
          />
        )}
      </Modal>

      <ConfirmDialog
        isOpen={!!pendingDelete}
        message={pendingDelete ? `Delete ${pendingDelete.name}? This cannot be undone.` : ''}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />
    </div>
  );
}

export default ProductsPage;
