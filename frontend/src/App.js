import React, { useEffect, useMemo, useState } from 'react';
import './App.css';
import { stockManagementAPI } from './utils/api';

const tabs = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'materials', label: 'Material Master' },
  { key: 'stock-in', label: 'Stock In / Purchases' },
  { key: 'stock-out', label: 'Stock Out / Issues' },
  { key: 'suppliers', label: 'Suppliers' },
  { key: 'settings', label: 'Settings' },
];

function Dashboard({ dashboard, onDownload }) {
  if (!dashboard) return null;

  return (
    <div className="panel">
      <div className="kpi-grid">
        <Kpi title="Total Stock Value" value={dashboard.total_stock_value} money />
        <Kpi title="Low Stock Items" value={dashboard.low_stock_items} />
        <Kpi title="Out of Stock" value={dashboard.out_of_stock_items} />
        <Kpi title="Purchase Value" value={dashboard.purchase_value} money />
      </div>

      <div className="row">
        <section>
          <div className="section-header">
            <h3>Low Stock Action List</h3>
            <button onClick={onDownload}>Download Excel</button>
          </div>
          <table>
            <thead>
              <tr>
                <th>Material</th>
                <th>Current</th>
                <th>Minimum</th>
                <th>Status</th>
                <th>Suggested</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.low_stock_action_list.map((item) => (
                <tr key={item.material}>
                  <td>{item.material}</td>
                  <td>{item.current_stock}</td>
                  <td>{item.minimum_stock}</td>
                  <td>{item.status}</td>
                  <td>{item.suggested_reorder_quantity}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section>
          <h3>Category Summary</h3>
          <table>
            <thead>
              <tr>
                <th>Category</th>
                <th>Items</th>
                <th>Stock Qty</th>
                <th>Stock Value</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.category_summary.map((item) => (
                <tr key={item.category}>
                  <td>{item.category}</td>
                  <td>{item.item_count}</td>
                  <td>{item.stock_quantity}</td>
                  <td>₹{Number(item.stock_value).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}

function Kpi({ title, value, money = false }) {
  return (
    <div className="kpi">
      <small>{title}</small>
      <strong>{money ? `₹${Number(value || 0).toFixed(2)}` : value ?? 0}</strong>
    </div>
  );
}

function App() {
  const [tab, setTab] = useState('dashboard');
  const [materials, setMaterials] = useState([]);
  const [stockInRows, setStockInRows] = useState([]);
  const [stockOutRows, setStockOutRows] = useState([]);
  const [suppliers, setSuppliers] = useState([]);
  const [settings, setSettings] = useState(null);
  const [dashboard, setDashboard] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [materialForm, setMaterialForm] = useState({ name: '', category: '', unit: 'sheet', opening_stock: 0, minimum_stock: 0, unit_price: 0, supplier_id: '' });
  const [stockInForm, setStockInForm] = useState({ material_id: '', quantity: 1, unit_price: '' });
  const [stockOutForm, setStockOutForm] = useState({ material_id: '', quantity: 1, issued_to: '' });
  const [supplierForm, setSupplierForm] = useState({ name: '', contact_person: '', phone: '' });

  const materialOptions = useMemo(() => materials.map((m) => ({ value: m.id, label: m.name })), [materials]);

  const refreshAll = async () => {
    setLoading(true);
    setError('');
    try {
      const [materialsRes, inRes, outRes, suppliersRes, settingsRes, dashboardRes] = await Promise.all([
        stockManagementAPI.getMaterials(),
        stockManagementAPI.getStockIn(),
        stockManagementAPI.getStockOut(),
        stockManagementAPI.getSuppliers(),
        stockManagementAPI.getSettings(),
        stockManagementAPI.getDashboard(),
      ]);

      setMaterials(materialsRes.data);
      setStockInRows(inRes.data);
      setStockOutRows(outRes.data);
      setSuppliers(suppliersRes.data);
      setSettings(settingsRes.data);
      setDashboard(dashboardRes.data);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to load stock management data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refreshAll();
  }, []);

  const submitMaterial = async (e) => {
    e.preventDefault();
    if (!materialForm.name || !materialForm.category) {
      setError('Material name and category are required.');
      return;
    }

    const payload = {
      ...materialForm,
      opening_stock: Number(materialForm.opening_stock || 0),
      minimum_stock: Number(materialForm.minimum_stock || 0),
      unit_price: Number(materialForm.unit_price || 0),
      supplier_id: materialForm.supplier_id ? Number(materialForm.supplier_id) : null,
    };

    try {
      await stockManagementAPI.createMaterial(payload);
      setMaterialForm({ name: '', category: '', unit: 'sheet', opening_stock: 0, minimum_stock: 0, unit_price: 0, supplier_id: '' });
      await refreshAll();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to add material.');
    }
  };

  const submitStockIn = async (e) => {
    e.preventDefault();
    if (!stockInForm.material_id) return setError('Select material for stock in.');
    try {
      await stockManagementAPI.createStockIn({
        material_id: Number(stockInForm.material_id),
        quantity: Number(stockInForm.quantity),
        unit_price: stockInForm.unit_price === '' ? null : Number(stockInForm.unit_price),
      });
      setStockInForm({ material_id: '', quantity: 1, unit_price: '' });
      await refreshAll();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to add stock-in entry.');
    }
  };

  const submitStockOut = async (e) => {
    e.preventDefault();
    if (!stockOutForm.material_id) return setError('Select material for stock out.');
    try {
      await stockManagementAPI.createStockOut({
        material_id: Number(stockOutForm.material_id),
        quantity: Number(stockOutForm.quantity),
        issued_to: stockOutForm.issued_to || null,
      });
      setStockOutForm({ material_id: '', quantity: 1, issued_to: '' });
      await refreshAll();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to add stock-out entry.');
    }
  };

  const submitSupplier = async (e) => {
    e.preventDefault();
    if (!supplierForm.name) return setError('Supplier name is required.');
    try {
      await stockManagementAPI.createSupplier(supplierForm);
      setSupplierForm({ name: '', contact_person: '', phone: '' });
      await refreshAll();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to add supplier.');
    }
  };

  const saveSettings = async (e) => {
    e.preventDefault();
    try {
      await stockManagementAPI.updateSettings({
        company_name: settings.company_name,
        currency: settings.currency,
        reorder_buffer: Number(settings.reorder_buffer),
      });
      await refreshAll();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to update settings.');
    }
  };

  const downloadExcel = async () => {
    try {
      const response = await stockManagementAPI.downloadExcel();
      const url = URL.createObjectURL(new Blob([response.data]));
      const a = document.createElement('a');
      a.href = url;
      a.download = 'stock-management-report.xlsx';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to download Excel report.');
    }
  };

  return (
    <div className="app">
      <header>
        <h1>Woodful Creations - Stock Management</h1>
        <p>Web + iPhone ready inventory workflow with Excel reporting</p>
      </header>

      <nav>
        {tabs.map((item) => (
          <button key={item.key} className={tab === item.key ? 'active' : ''} onClick={() => setTab(item.key)}>
            {item.label}
          </button>
        ))}
      </nav>

      {error && <div className="error">{error}</div>}
      {loading ? <div className="panel">Loading...</div> : null}

      {!loading && tab === 'dashboard' && <Dashboard dashboard={dashboard} onDownload={downloadExcel} />}

      {!loading && tab === 'materials' && (
        <div className="panel">
          <h3>Material Master</h3>
          <form className="form-grid" onSubmit={submitMaterial}>
            <input placeholder="Material name" value={materialForm.name} onChange={(e) => setMaterialForm({ ...materialForm, name: e.target.value })} />
            <input placeholder="Category" value={materialForm.category} onChange={(e) => setMaterialForm({ ...materialForm, category: e.target.value })} />
            <input placeholder="Unit" value={materialForm.unit} onChange={(e) => setMaterialForm({ ...materialForm, unit: e.target.value })} />
            <input type="number" placeholder="Opening stock" value={materialForm.opening_stock} onChange={(e) => setMaterialForm({ ...materialForm, opening_stock: e.target.value })} />
            <input type="number" placeholder="Minimum stock" value={materialForm.minimum_stock} onChange={(e) => setMaterialForm({ ...materialForm, minimum_stock: e.target.value })} />
            <input type="number" placeholder="Unit price" value={materialForm.unit_price} onChange={(e) => setMaterialForm({ ...materialForm, unit_price: e.target.value })} />
            <select value={materialForm.supplier_id} onChange={(e) => setMaterialForm({ ...materialForm, supplier_id: e.target.value })}>
              <option value="">Supplier (optional)</option>
              {suppliers.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
            <button type="submit">Add Material</button>
          </form>
          <table>
            <thead><tr><th>Name</th><th>Category</th><th>Current</th><th>Minimum</th><th>Status</th></tr></thead>
            <tbody>
              {materials.map((m) => <tr key={m.id}><td>{m.name}</td><td>{m.category}</td><td>{m.current_stock}</td><td>{m.minimum_stock}</td><td>{m.status}</td></tr>)}
            </tbody>
          </table>
        </div>
      )}

      {!loading && tab === 'stock-in' && (
        <div className="panel">
          <h3>Stock In / Purchase Register</h3>
          <form className="form-grid" onSubmit={submitStockIn}>
            <select value={stockInForm.material_id} onChange={(e) => setStockInForm({ ...stockInForm, material_id: e.target.value })}>
              <option value="">Select material</option>
              {materialOptions.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
            <input type="number" min="0.01" step="0.01" value={stockInForm.quantity} onChange={(e) => setStockInForm({ ...stockInForm, quantity: e.target.value })} />
            <input type="number" min="0" step="0.01" placeholder="Unit price (optional)" value={stockInForm.unit_price} onChange={(e) => setStockInForm({ ...stockInForm, unit_price: e.target.value })} />
            <button type="submit">Add Purchase</button>
          </form>
          <table>
            <thead><tr><th>Date</th><th>Material ID</th><th>Qty</th><th>Unit Price</th></tr></thead>
            <tbody>{stockInRows.map((r) => <tr key={r.id}><td>{new Date(r.purchased_at).toLocaleString()}</td><td>{r.material_id}</td><td>{r.quantity}</td><td>{r.unit_price ?? '-'}</td></tr>)}</tbody>
          </table>
        </div>
      )}

      {!loading && tab === 'stock-out' && (
        <div className="panel">
          <h3>Stock Out / Material Issue Register</h3>
          <form className="form-grid" onSubmit={submitStockOut}>
            <select value={stockOutForm.material_id} onChange={(e) => setStockOutForm({ ...stockOutForm, material_id: e.target.value })}>
              <option value="">Select material</option>
              {materialOptions.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
            <input type="number" min="0.01" step="0.01" value={stockOutForm.quantity} onChange={(e) => setStockOutForm({ ...stockOutForm, quantity: e.target.value })} />
            <input placeholder="Issued to" value={stockOutForm.issued_to} onChange={(e) => setStockOutForm({ ...stockOutForm, issued_to: e.target.value })} />
            <button type="submit">Add Issue</button>
          </form>
          <table>
            <thead><tr><th>Date</th><th>Material ID</th><th>Qty</th><th>Issued To</th></tr></thead>
            <tbody>{stockOutRows.map((r) => <tr key={r.id}><td>{new Date(r.issued_at).toLocaleString()}</td><td>{r.material_id}</td><td>{r.quantity}</td><td>{r.issued_to ?? '-'}</td></tr>)}</tbody>
          </table>
        </div>
      )}

      {!loading && tab === 'suppliers' && (
        <div className="panel">
          <h3>Suppliers</h3>
          <form className="form-grid" onSubmit={submitSupplier}>
            <input placeholder="Name" value={supplierForm.name} onChange={(e) => setSupplierForm({ ...supplierForm, name: e.target.value })} />
            <input placeholder="Contact Person" value={supplierForm.contact_person} onChange={(e) => setSupplierForm({ ...supplierForm, contact_person: e.target.value })} />
            <input placeholder="Phone" value={supplierForm.phone} onChange={(e) => setSupplierForm({ ...supplierForm, phone: e.target.value })} />
            <button type="submit">Add Supplier</button>
          </form>
          <table>
            <thead><tr><th>Name</th><th>Contact</th><th>Phone</th></tr></thead>
            <tbody>{suppliers.map((s) => <tr key={s.id}><td>{s.name}</td><td>{s.contact_person || '-'}</td><td>{s.phone || '-'}</td></tr>)}</tbody>
          </table>
        </div>
      )}

      {!loading && tab === 'settings' && settings && (
        <div className="panel">
          <h3>Settings</h3>
          <form className="form-grid" onSubmit={saveSettings}>
            <input value={settings.company_name} onChange={(e) => setSettings({ ...settings, company_name: e.target.value })} />
            <input value={settings.currency} onChange={(e) => setSettings({ ...settings, currency: e.target.value })} />
            <input type="number" min="1" step="0.1" value={settings.reorder_buffer} onChange={(e) => setSettings({ ...settings, reorder_buffer: e.target.value })} />
            <button type="submit">Save Settings</button>
          </form>
        </div>
      )}
    </div>
  );
}

export default App;
