import React, { useState, useEffect, useCallback } from 'react';
import { salesAPI, reportsAPI } from '../utils/api';

const STATUS_OPTIONS = ['pending', 'confirmed', 'in_progress', 'delivered', 'cancelled'];

const EMPTY_ITEM = { product_name: '', quantity: 1, unit_price: 0 };
const EMPTY_FORM = {
  client_name: '',
  client_phone: '',
  client_email: '',
  notes: '',
  items: [{ ...EMPTY_ITEM }],
};

function SalesOrdersPage() {
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);
  const [formData, setFormData] = useState(EMPTY_FORM);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [downloading, setDownloading] = useState(false);

  const fetchOrders = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const params = {};
      if (search) params.search = search;
      if (statusFilter) params.status = statusFilter;
      const res = await salesAPI.getOrders(params);
      setOrders(res.data);
    } catch (err) {
      setError('Failed to load orders.');
    } finally {
      setLoading(false);
    }
  }, [search, statusFilter]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const handleItemChange = (index, field, value) => {
    const items = formData.items.map((item, i) =>
      i === index ? { ...item, [field]: value } : item
    );
    setFormData({ ...formData, items });
  };

  const addItem = () =>
    setFormData({ ...formData, items: [...formData.items, { ...EMPTY_ITEM }] });

  const removeItem = (index) =>
    setFormData({
      ...formData,
      items: formData.items.filter((_, i) => i !== index),
    });

  const orderTotal = formData.items.reduce(
    (sum, item) => sum + Number(item.quantity) * Number(item.unit_price),
    0
  );

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (formData.items.length === 0) {
      alert('Add at least one item.');
      return;
    }
    try {
      await salesAPI.createOrder({
        ...formData,
        items: formData.items.map((item) => ({
          ...item,
          quantity: Number(item.quantity),
          unit_price: Number(item.unit_price),
        })),
      });
      setFormData(EMPTY_FORM);
      setShowForm(false);
      fetchOrders();
    } catch (err) {
      alert('Failed to create order.');
    }
  };

  const handleStatusUpdate = async (id, status) => {
    try {
      await salesAPI.updateOrder(id, { status });
      fetchOrders();
    } catch {
      alert('Failed to update order.');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this order?')) return;
    try {
      await salesAPI.deleteOrder(id);
      if (selectedOrder?.id === id) setSelectedOrder(null);
      fetchOrders();
    } catch {
      alert('Failed to delete order.');
    }
  };

  const downloadExcel = async () => {
    setDownloading(true);
    try {
      const res = await reportsAPI.downloadSalesExcel();
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'sales_report.xlsx');
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
    } catch {
      alert('Failed to download report.');
    } finally {
      setDownloading(false);
    }
  };

  const statusBadgeStyle = (status) => {
    const colors = {
      pending: '#f59e0b',
      confirmed: '#3b82f6',
      in_progress: '#8b5cf6',
      delivered: '#10b981',
      cancelled: '#ef4444',
    };
    return {
      backgroundColor: colors[status] || '#6b7280',
      color: '#fff',
      padding: '2px 8px',
      borderRadius: '12px',
      fontSize: '12px',
      fontWeight: 600,
    };
  };

  return (
    <div style={{ padding: '24px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 700 }}>Sales Orders</h1>
        <div style={{ display: 'flex', gap: '10px' }}>
          <button
            onClick={downloadExcel}
            disabled={downloading}
            style={{
              padding: '8px 16px',
              background: '#10b981',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: 600,
            }}
          >
            {downloading ? 'Downloading...' : 'Download Excel'}
          </button>
          <button
            onClick={() => setShowForm(!showForm)}
            style={{
              padding: '8px 16px',
              background: showForm ? '#6b7280' : '#4f46e5',
              color: '#fff',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer',
              fontWeight: 600,
            }}
          >
            {showForm ? 'Cancel' : 'New Order'}
          </button>
        </div>
      </div>

      {showForm && (
        <div style={{ background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '20px', marginBottom: '24px' }}>
          <h2 style={{ margin: '0 0 16px', fontSize: '18px' }}>Create Sales Order</h2>
          <form onSubmit={handleSubmit}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', marginBottom: '16px' }}>
              <div>
                <label style={{ display: 'block', marginBottom: '4px', fontWeight: 600, fontSize: '13px' }}>Client Name *</label>
                <input
                  type="text"
                  value={formData.client_name}
                  onChange={(e) => setFormData({ ...formData, client_name: e.target.value })}
                  required
                  style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px', boxSizing: 'border-box' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '4px', fontWeight: 600, fontSize: '13px' }}>Phone</label>
                <input
                  type="text"
                  value={formData.client_phone}
                  onChange={(e) => setFormData({ ...formData, client_phone: e.target.value })}
                  style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px', boxSizing: 'border-box' }}
                />
              </div>
              <div>
                <label style={{ display: 'block', marginBottom: '4px', fontWeight: 600, fontSize: '13px' }}>Email</label>
                <input
                  type="email"
                  value={formData.client_email}
                  onChange={(e) => setFormData({ ...formData, client_email: e.target.value })}
                  style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px', boxSizing: 'border-box' }}
                />
              </div>
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ display: 'block', marginBottom: '4px', fontWeight: 600, fontSize: '13px' }}>Notes</label>
              <textarea
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                rows={2}
                style={{ width: '100%', padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px', boxSizing: 'border-box' }}
              />
            </div>

            <div style={{ marginBottom: '12px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontWeight: 600, fontSize: '14px' }}>Order Items</span>
                <button
                  type="button"
                  onClick={addItem}
                  style={{ padding: '4px 12px', background: '#4f46e5', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '13px' }}
                >
                  + Add Item
                </button>
              </div>
              {formData.items.map((item, index) => (
                <div key={index} style={{ display: 'grid', gridTemplateColumns: '2fr 1fr 1fr auto', gap: '8px', marginBottom: '8px', alignItems: 'center' }}>
                  <input
                    type="text"
                    placeholder="Product name *"
                    value={item.product_name}
                    onChange={(e) => handleItemChange(index, 'product_name', e.target.value)}
                    required
                    style={{ padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px' }}
                  />
                  <input
                    type="number"
                    placeholder="Qty"
                    min="1"
                    value={item.quantity}
                    onChange={(e) => handleItemChange(index, 'quantity', e.target.value)}
                    required
                    style={{ padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px' }}
                  />
                  <input
                    type="number"
                    placeholder="Unit price"
                    min="0"
                    step="0.01"
                    value={item.unit_price}
                    onChange={(e) => handleItemChange(index, 'unit_price', e.target.value)}
                    required
                    style={{ padding: '8px', border: '1px solid #d1d5db', borderRadius: '4px' }}
                  />
                  <button
                    type="button"
                    onClick={() => removeItem(index)}
                    style={{ padding: '8px 10px', background: '#ef4444', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
                    disabled={formData.items.length === 1}
                  >
                    X
                  </button>
                </div>
              ))}
              <div style={{ textAlign: 'right', fontWeight: 700, fontSize: '15px', marginTop: '8px' }}>
                Total: Rs {orderTotal.toFixed(2)}
              </div>
            </div>

            <button
              type="submit"
              style={{ padding: '10px 24px', background: '#4f46e5', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontWeight: 600, fontSize: '14px' }}
            >
              Create Order
            </button>
          </form>
        </div>
      )}

      <div style={{ display: 'flex', gap: '12px', marginBottom: '20px' }}>
        <input
          type="text"
          placeholder="Search by client or order number..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ flex: 1, padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px' }}
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          style={{ padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '6px' }}
        >
          <option value="">All Statuses</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1).replace('_', ' ')}</option>
          ))}
        </select>
      </div>

      {error && <div style={{ color: '#ef4444', marginBottom: '16px' }}>{error}</div>}

      {loading ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#6b7280' }}>Loading orders...</div>
      ) : orders.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px', color: '#6b7280' }}>No orders found.</div>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '14px' }}>
            <thead>
              <tr style={{ background: '#f3f4f6' }}>
                {['Order No.', 'Client', 'Phone', 'Status', 'Total (Rs)', 'Date', 'Actions'].map((h) => (
                  <th key={h} style={{ padding: '10px 12px', textAlign: 'left', fontWeight: 600, borderBottom: '2px solid #e5e7eb' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {orders.map((order) => (
                <tr
                  key={order.id}
                  style={{ borderBottom: '1px solid #e5e7eb', cursor: 'pointer', background: selectedOrder?.id === order.id ? '#eff6ff' : '#fff' }}
                  onClick={() => setSelectedOrder(selectedOrder?.id === order.id ? null : order)}
                >
                  <td style={{ padding: '10px 12px', fontWeight: 600 }}>{order.order_number}</td>
                  <td style={{ padding: '10px 12px' }}>{order.client_name}</td>
                  <td style={{ padding: '10px 12px', color: '#6b7280' }}>{order.client_phone || '-'}</td>
                  <td style={{ padding: '10px 12px' }}>
                    <span style={statusBadgeStyle(order.status)}>
                      {order.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td style={{ padding: '10px 12px', fontWeight: 600 }}>{Number(order.total_amount).toFixed(2)}</td>
                  <td style={{ padding: '10px 12px', color: '#6b7280' }}>
                    {new Date(order.created_at).toLocaleDateString()}
                  </td>
                  <td style={{ padding: '10px 12px' }} onClick={(e) => e.stopPropagation()}>
                    <select
                      value={order.status}
                      onChange={(e) => handleStatusUpdate(order.id, e.target.value)}
                      style={{ padding: '4px 6px', border: '1px solid #d1d5db', borderRadius: '4px', marginRight: '6px', fontSize: '12px' }}
                    >
                      {STATUS_OPTIONS.map((s) => (
                        <option key={s} value={s}>{s.replace('_', ' ')}</option>
                      ))}
                    </select>
                    <button
                      onClick={() => handleDelete(order.id)}
                      style={{ padding: '4px 8px', background: '#ef4444', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedOrder && (
        <div style={{ marginTop: '24px', background: '#f9fafb', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '20px' }}>
          <h3 style={{ margin: '0 0 12px', fontSize: '16px', fontWeight: 700 }}>
            Order Details: {selectedOrder.order_number}
          </h3>
          {selectedOrder.notes && (
            <p style={{ margin: '0 0 12px', color: '#6b7280', fontSize: '13px' }}>Notes: {selectedOrder.notes}</p>
          )}
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '13px' }}>
            <thead>
              <tr style={{ background: '#e5e7eb' }}>
                {['Product', 'Quantity', 'Unit Price (Rs)', 'Line Total (Rs)'].map((h) => (
                  <th key={h} style={{ padding: '8px 10px', textAlign: 'left', fontWeight: 600 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(selectedOrder.items || []).map((item) => (
                <tr key={item.id} style={{ borderBottom: '1px solid #e5e7eb' }}>
                  <td style={{ padding: '8px 10px' }}>{item.product_name}</td>
                  <td style={{ padding: '8px 10px' }}>{item.quantity}</td>
                  <td style={{ padding: '8px 10px' }}>{Number(item.unit_price).toFixed(2)}</td>
                  <td style={{ padding: '8px 10px', fontWeight: 600 }}>{Number(item.line_total).toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div style={{ textAlign: 'right', fontWeight: 700, marginTop: '10px', fontSize: '15px' }}>
            Total: Rs {Number(selectedOrder.total_amount).toFixed(2)}
          </div>
        </div>
      )}
    </div>
  );
}

export default SalesOrdersPage;
