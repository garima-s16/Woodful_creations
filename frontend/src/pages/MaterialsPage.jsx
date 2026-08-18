import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useDispatch, useSelector } from 'react-redux';
import { materialsAPI, materialCategoriesAPI, locationsAPI, suppliersAPI, reportsAPI } from '../utils/api';
import { addToCart } from '../redux/slices/cartSlice';
import Table from '../components/common/Table';
import Modal from '../components/common/Modal';
import ConfirmDialog from '../components/common/ConfirmDialog';
import Form from '../components/common/Form';
import MaterialAttributesEditor from '../components/MaterialAttributesEditor';
import Alert from '../components/common/Alert';
import KpiCard from '../components/common/KpiCard';
import Pagination from '../components/common/Pagination';
import MaterialCard from '../components/common/MaterialCard';
import { GridIcon, ListIcon, SlidersIcon, SearchIcon, CartIcon } from '../components/icons';
import { formatCurrency } from '../utils/currency';
import { statusClass } from '../utils/statusColors';
import '../styles/components/MaterialCatalog.css';

const PAGE_SIZE = 25;
const SORT_OPTIONS = [
  { value: 'name-asc', label: 'Name (A-Z)' },
  { value: 'price-asc', label: 'Price: Low to High' },
  { value: 'price-desc', label: 'Price: High to Low' },
  { value: 'stock-asc', label: 'Stock: Low to High' },
  { value: 'stock-desc', label: 'Stock: High to Low' },
];

function MaterialsPage() {
  const navigate = useNavigate();
  const dispatch = useDispatch();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const isStrictlyMaster = user?.role === 'master';
  const location = useLocation();

  const [materials, setMaterials] = useState([]);
  const [allMaterials, setAllMaterials] = useState([]); // unfiltered, for KPIs + filter option lists
  const [suppliers, setSuppliers] = useState([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [brand, setBrand] = useState('');
  const [thickness, setThickness] = useState('');
  const [sort, setSort] = useState('name-asc');
  const [lowStockOnly, setLowStockOnly] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [filterCategories, setFilterCategories] = useState([]);
  const [filterCategoryId, setFilterCategoryId] = useState('');
  const [filterSubcategoryId, setFilterSubcategoryId] = useState('');
  const [filterAttributeDefs, setFilterAttributeDefs] = useState([]);
  const [filterAttributeValues, setFilterAttributeValues] = useState({}); // attribute_definition_id -> value
  const [allLocations, setAllLocations] = useState([]);
  const [view, setView] = useState('grid'); // grid | list | table
  const [showAdd, setShowAdd] = useState(!!location.state?.openCreate);
  const [editingMaterial, setEditingMaterial] = useState(null);
  const [error, setError] = useState('');
  const [addedFlash, setAddedFlash] = useState(null);
  const [loading, setLoading] = useState(false);
  const [hierarchySelection, setHierarchySelection] = useState({ subcategoryId: null, attributeValues: [] });
  const [pageLoading, setPageLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  const load = (params, pageNum = 1) => {
    const offset = (pageNum - 1) * PAGE_SIZE;
    setPageLoading(true);
    setError('');
    materialsAPI.list({ ...params, limit: PAGE_SIZE, offset }).then((res) => {
      setMaterials(res.data);
      setTotalCount(Number(res.headers['x-total-count'] || res.data.length));
    }).catch(() => {
      setMaterials([]);
      setTotalCount(0);
      setError('Could not load materials. Check that the backend server is running and reachable.');
    }).finally(() => setPageLoading(false));
    materialsAPI.list().then((res) => setAllMaterials(res.data)).catch(() => setAllMaterials([]));
    suppliersAPI.list().then((res) => setSuppliers(res.data)).catch(() => setSuppliers([]));
    materialCategoriesAPI.list().then((res) => setFilterCategories(res.data)).catch(() => setFilterCategories([]));
    locationsAPI.list().then((res) => setAllLocations(res.data)).catch(() => setAllLocations([]));
  };

  useEffect(() => load(), []); // eslint-disable-line react-hooks/exhaustive-deps

  // Server-side filters: search, category, low-stock, and now the real
  // dynamic subcategory/attribute filters (built server-side against
  // MaterialAttributeValue, not client-side against the legacy
  // brand_grade/thickness_size strings). These reset pagination.
  const serverFilters = () => {
    const params = {};
    if (search) params.search = search;
    if (category) params.category = category;
    if (lowStockOnly) params.low_stock_only = true;
    if (filterSubcategoryId) params.subcategory_id = filterSubcategoryId;
    const activeAttrFilters = Object.entries(filterAttributeValues).filter(([, v]) => v);
    if (activeAttrFilters.length > 0) params.attribute_filters = JSON.stringify(Object.fromEntries(activeAttrFilters));
    return params;
  };

  const applyServerFilters = (e) => {
    e?.preventDefault();
    setPage(1);
    load(serverFilters(), 1);
  };

  const handleFilterCategoryChange = (e) => {
    const id = e.target.value;
    setFilterCategoryId(id);
    setFilterSubcategoryId('');
    setFilterAttributeDefs([]);
    setFilterAttributeValues({});
  };

  const handleFilterSubcategoryChange = (e) => {
    const id = e.target.value;
    setFilterSubcategoryId(id);
    setFilterAttributeValues({});
    if (!id) {
      setFilterAttributeDefs([]);
      return;
    }
    const cat = filterCategories.find((c) => String(c.id) === filterCategoryId);
    const sub = cat?.subcategories.find((s) => String(s.id) === id);
    setFilterAttributeDefs(sub?.attribute_definitions || []);
  };

  const handleFilterAttributeChange = (attrId, value) => {
    setFilterAttributeValues((prev) => ({ ...prev, [attrId]: value }));
  };

  const selectCategory = (cat) => {
    setCategory(cat);
    setPage(1);
    load({ ...serverFilters(), category: cat || undefined }, 1);
  };

  const goToPage = (pageNum) => {
    setPage(pageNum);
    load(serverFilters(), pageNum);
  };

  // Brand/thickness/sort are refined client-side on the current page,
  // since the backend doesn't expose those as query filters yet.
  const categories = useMemo(
    () => [...new Set(allMaterials.map((m) => m.category).filter(Boolean))].sort(),
    [allMaterials]
  );
  const brands = useMemo(
    () => [...new Set(allMaterials.map((m) => m.brand_grade).filter(Boolean))].sort(),
    [allMaterials]
  );
  const thicknesses = useMemo(
    () => [...new Set(allMaterials.map((m) => m.thickness_size).filter(Boolean))].sort(),
    [allMaterials]
  );

  const visibleMaterials = useMemo(() => {
    let list = materials.filter((m) => (!brand || m.brand_grade === brand) && (!thickness || m.thickness_size === thickness));
    const [field, dir] = sort.split('-');
    list = [...list].sort((a, b) => {
      let diff = 0;
      if (field === 'name') diff = (a.name || '').localeCompare(b.name || '');
      if (field === 'price') diff = (Number(a.average_rate) || 0) - (Number(b.average_rate) || 0);
      if (field === 'stock') diff = (Number(a.current_stock) || 0) - (Number(b.current_stock) || 0);
      return dir === 'desc' ? -diff : diff;
    });
    return list;
  }, [materials, brand, thickness, sort]);

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
        location_id: formData.location_id ? Number(formData.location_id) : null,
        subcategory_id: hierarchySelection.subcategoryId,
        attribute_values: hierarchySelection.attributeValues,
      });
      setShowAdd(false);
      setHierarchySelection({ subcategoryId: null, attributeValues: [] });
      applyServerFilters();
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
        location_id: formData.location_id ? Number(formData.location_id) : null,
        subcategory_id: hierarchySelection.subcategoryId,
        attribute_values: hierarchySelection.attributeValues,
      });
      setEditingMaterial(null);
      applyServerFilters();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update material');
    } finally {
      setLoading(false);
    }
  };

  const [pendingDelete, setPendingDelete] = useState(null);
  const handleDelete = (material) => setPendingDelete(material);
  const confirmDelete = async () => {
    setError('');
    try {
      await materialsAPI.remove(pendingDelete.id);
      setPendingDelete(null);
      applyServerFilters();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete material');
      setPendingDelete(null);
    }
  };

  const handleAddToCart = (material, qty) => {
    const supplier = suppliers.find((s) => s.id === material.supplier_id);
    dispatch(addToCart({
      materialId: material.id,
      name: material.name,
      unit: material.unit,
      rate: material.average_rate,
      supplierId: material.supplier_id,
      supplierName: supplier?.name,
      quantity: qty,
      currentStock: material.current_stock,
    }));
    setAddedFlash(material.id);
    setTimeout(() => setAddedFlash(null), 1200);
  };

  const columns = [
    { key: 'material_code', label: 'Material ID' }, { key: 'name', label: 'Name' },
    { key: 'category', label: 'Category' }, { key: 'unit', label: 'Unit' },
    { key: 'current_stock', label: 'Available Stock' }, { key: 'minimum_stock', label: 'Reorder Level' },
    { key: 'stock_status', label: 'Status', render: (v) => <span className={`status-badge ${statusClass(v)}`}>{v}</span> },
    { key: 'average_rate', label: 'Avg Rate', render: (v) => v != null ? formatCurrency(v) : 'Restricted' },
    { key: 'stock_value', label: 'Stock Value', render: (v) => v != null ? formatCurrency(v) : 'Restricted' },
    { key: 'location', label: 'Location' },
    {
      key: 'edit_action', label: '', render: (v, row) => (
        isPrivileged ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); setEditingMaterial(row); }}>Edit</button> : null
      ),
    },
    {
      key: 'delete_action', label: '', render: (v, row) => (
        isStrictlyMaster ? <button className="btn-link" onClick={(e) => { e.stopPropagation(); handleDelete(row); }}>Delete</button> : null
      ),
    },
  ];

  const createFields = [
    { name: 'name', label: 'Name', required: true, section: 'Identity' },
    { name: 'unit', label: 'Unit', required: true, placeholder: 'Sheets', section: 'Identity' },
    { name: 'opening_stock', label: 'Opening Stock', type: 'number', section: 'Inventory' },
    { name: 'minimum_stock', label: 'Reorder Level', type: 'number', section: 'Inventory' },
    { name: 'average_rate', label: 'Average Rate', type: 'number', section: 'Inventory' },
    { name: 'supplier_id', label: 'Primary Supplier', type: 'select', options: suppliers.map((s) => ({ value: s.id, label: s.name })), section: 'Supplier & Location' },
    { name: 'location_id', label: 'Location', type: 'select', options: allLocations.map((l) => ({ value: l.id, label: l.full_path })), section: 'Supplier & Location' },
    // Legacy fields, kept for backward compatibility but deliberately not
    // shown alongside the primary fields above - the real
    // category/specifications entry is MaterialAttributesEditor, rendered
    // above this form. These only matter for edge cases (a category that
    // doesn't fit the new hierarchy yet, or migrating old data by hand).
    { name: 'category', label: 'Category (only if not using Category/Subcategory above)', section: 'Legacy Fields (optional)' },
    { name: 'brand_grade', label: 'Brand/Grade (only if not using Specifications above)', section: 'Legacy Fields (optional)' },
    { name: 'thickness_size', label: 'Thickness/Size (only if not using Specifications above)', section: 'Legacy Fields (optional)' },
    { name: 'location', label: 'Location (free text, only if not using the Location dropdown above)', section: 'Legacy Fields (optional)' },
  ];

  const editFields = createFields
    .filter((f) => !['opening_stock'].includes(f.name))
    .map(({ section, ...rest }) => rest);

  const inventoryValue = allMaterials.reduce((sum, m) => sum + (m.stock_value || 0), 0);
  const lowStockCount = allMaterials.filter((m) => m.stock_status === 'LOW STOCK').length;
  const outOfStockCount = allMaterials.filter((m) => m.stock_status === 'OUT OF STOCK').length;

  const hasAnyMaterials = allMaterials.length > 0;
  const activeFilterCount = [category, brand, thickness, lowStockOnly].filter(Boolean).length;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Material Catalog</h1>
          <p className="page-summary">Browse, compare, and stock up on every material Woodful works with.</p>
        </div>
        <div className="page-actions">
          <a className="btn-secondary" href={reportsAPI.downloadUrl('stock-dashboard.xlsx')} target="_blank" rel="noreferrer">
            Export Stock Dashboard
          </a>
          {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Material</button>}
        </div>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      <div className="kpi-row">
        {isPrivileged && <KpiCard label="Inventory Value" value={formatCurrency(inventoryValue)} />}
        <KpiCard label="Low Stock" value={lowStockCount} tone={lowStockCount > 0 ? 'warning' : 'success'} />
        <KpiCard label="Out of Stock" value={outOfStockCount} tone={outOfStockCount > 0 ? 'danger' : 'success'} />
      </div>

      {hasAnyMaterials && (
        <>
          {categories.length > 0 && (
            <div className="category-pills">
              <button className={`category-pill ${!category ? 'active' : ''}`} onClick={() => selectCategory('')}>All</button>
              {categories.map((c) => (
                <button key={c} className={`category-pill ${category === c ? 'active' : ''}`} onClick={() => selectCategory(c)}>{c}</button>
              ))}
            </div>
          )}

          <div className="catalog-toolbar">
            <form className="catalog-search" onSubmit={applyServerFilters}>
              <SearchIcon width={16} height={16} />
              <input
                type="text" placeholder="Search materials by name or code..." value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
              <button type="submit" className="btn-secondary catalog-search-btn">Search</button>
            </form>

            <button
              className={`btn-secondary catalog-filter-toggle ${activeFilterCount ? 'has-active' : ''}`}
              onClick={() => setShowFilters((v) => !v)}
            >
              <SlidersIcon width={15} height={15} /> Filters {activeFilterCount > 0 && <span className="filter-count">{activeFilterCount}</span>}
            </button>

            <select className="catalog-sort" value={sort} onChange={(e) => setSort(e.target.value)}>
              {SORT_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>

            <div className="view-toggle">
              <button className={view === 'grid' ? 'active' : ''} onClick={() => setView('grid')} title="Grid view" aria-label="Grid view"><GridIcon width={16} height={16} /></button>
              <button className={view === 'list' ? 'active' : ''} onClick={() => setView('list')} title="List view" aria-label="List view"><ListIcon width={16} height={16} /></button>
              <button className={view === 'table' ? 'active' : ''} onClick={() => setView('table')} title="Table view" aria-label="Table view">Table</button>
            </div>
          </div>

          {showFilters && (
            <div className="catalog-filter-panel">
              <label className="catalog-filter-field">
                Category
                <select value={filterCategoryId} onChange={handleFilterCategoryChange}>
                  <option value="">All categories</option>
                  {filterCategories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                </select>
              </label>
              {filterCategoryId && (
                <label className="catalog-filter-field">
                  Subcategory
                  <select value={filterSubcategoryId} onChange={handleFilterSubcategoryChange}>
                    <option value="">All subcategories</option>
                    {(filterCategories.find((c) => String(c.id) === filterCategoryId)?.subcategories || [])
                      .map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </label>
              )}
              {filterAttributeDefs.map((def) => (
                <label className="catalog-filter-field" key={def.id}>
                  {def.name}{def.unit_label && ` (${def.unit_label})`}
                  {def.data_type === 'select' ? (
                    <select value={filterAttributeValues[def.id] || ''} onChange={(e) => handleFilterAttributeChange(def.id, e.target.value)}>
                      <option value="">Any {def.name}</option>
                      {(def.select_options || '').split(',').map((o) => o.trim()).filter(Boolean).map((o) => (
                        <option key={o} value={o}>{o}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type={def.data_type === 'number' ? 'number' : 'text'}
                      value={filterAttributeValues[def.id] || ''}
                      onChange={(e) => handleFilterAttributeChange(def.id, e.target.value)}
                      placeholder={`Any ${def.name}`}
                    />
                  )}
                </label>
              ))}
              {!filterSubcategoryId && brands.length > 0 && (
                <label className="catalog-filter-field">
                  Brand / Grade (legacy)
                  <select value={brand} onChange={(e) => setBrand(e.target.value)}>
                    <option value="">All brands</option>
                    {brands.map((b) => <option key={b} value={b}>{b}</option>)}
                  </select>
                </label>
              )}
              {!filterSubcategoryId && thicknesses.length > 0 && (
                <label className="catalog-filter-field">
                  Thickness / Size (legacy)
                  <select value={thickness} onChange={(e) => setThickness(e.target.value)}>
                    <option value="">All sizes</option>
                    {thicknesses.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select>
                </label>
              )}
              <label className="catalog-filter-field catalog-filter-checkbox">
                <input type="checkbox" checked={lowStockOnly} onChange={(e) => setLowStockOnly(e.target.checked)} />
                Low stock only
              </label>
              <button className="btn-secondary" onClick={applyServerFilters}>Apply</button>
              <button
                className="btn-link"
                onClick={() => {
                  setBrand(''); setThickness(''); setLowStockOnly(false); setCategory(''); setSearch('');
                  setFilterCategoryId(''); setFilterSubcategoryId(''); setFilterAttributeDefs([]); setFilterAttributeValues({});
                  setPage(1); load({}, 1);
                }}
              >
                Clear all
              </button>
            </div>
          )}
        </>
      )}

      {!hasAnyMaterials && !pageLoading ? (
        <div className="catalog-empty-state">
          <div className="catalog-empty-icon"><CartIcon width={28} height={28} /></div>
          <h3>No materials in the catalog yet</h3>
          <p>Add your first material to start browsing stock, prices, and suppliers in one place.</p>
          {isPrivileged && <button className="btn-primary" onClick={() => setShowAdd(true)}>Add Material</button>}
        </div>
      ) : view === 'table' ? (
        <>
          <Table columns={columns} data={visibleMaterials} loading={pageLoading} onRowClick={(row) => navigate(`/materials/${row.id}`)} emptyMessage="No materials match your filters." />
          {totalCount > PAGE_SIZE && (
            <Pagination currentPage={page} totalPages={Math.ceil(totalCount / PAGE_SIZE)} onPageChange={goToPage} />
          )}
        </>
      ) : pageLoading ? (
        <div className={view === 'grid' ? 'material-grid' : 'material-list'}>
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className={view === 'grid' ? 'material-card-skeleton' : 'material-row-skeleton'} />
          ))}
        </div>
      ) : visibleMaterials.length === 0 ? (
        <div className="catalog-empty-state">
          <h3>No materials match your filters</h3>
          <p>Try a different search term, or clear filters to see the full catalog.</p>
          <button className="btn-secondary" onClick={() => { setBrand(''); setThickness(''); setLowStockOnly(false); setCategory(''); setSearch(''); setPage(1); load({}, 1); }}>Clear filters</button>
        </div>
      ) : (
        <>
          <div className={view === 'grid' ? 'material-grid' : 'material-list'}>
            {visibleMaterials.map((m) => (
              <div key={m.id} className={addedFlash === m.id ? 'material-card-added' : ''}>
                <MaterialCard material={m} view={view} onOpen={(mat) => navigate(`/materials/${mat.id}`)} onAddToCart={handleAddToCart} />
              </div>
            ))}
          </div>
          {totalCount > PAGE_SIZE && (
            <Pagination currentPage={page} totalPages={Math.ceil(totalCount / PAGE_SIZE)} onPageChange={goToPage} />
          )}
        </>
      )}

      <Modal isOpen={showAdd} title="Add Material" onClose={() => { setShowAdd(false); setHierarchySelection({ subcategoryId: null, attributeValues: [] }); }}>
        <MaterialAttributesEditor onChange={setHierarchySelection} />
        <Form fields={createFields} onSubmit={handleCreate} loading={loading} submitText="Add Material" />
      </Modal>
      <Modal isOpen={!!editingMaterial} title={`Edit ${editingMaterial?.name || ''}`} onClose={() => { setEditingMaterial(null); setHierarchySelection({ subcategoryId: null, attributeValues: [] }); }}>
        {editingMaterial && (
          <>
            <MaterialAttributesEditor
              onChange={setHierarchySelection}
              initialSubcategoryId={editingMaterial.subcategory_id}
              initialAttributeValues={editingMaterial.attribute_values}
            />
            <Form fields={editFields} onSubmit={handleUpdate} loading={loading} submitText="Save Changes" initialValues={editingMaterial} />
          </>
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

export default MaterialsPage;
