import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { productsAPI, reportsAPI } from '../utils/api';
import Card from '../components/common/Card';
import ConfirmDialog from '../components/common/ConfirmDialog';
import { formatCurrency } from '../utils/currency';

function ProductDetailPage() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isMaster = user?.role === 'master';

  const [product, setProduct] = useState(null);
  const [loading, setLoading] = useState(true);
  const [pendingDelete, setPendingDelete] = useState(false);
  const [error, setError] = useState('');

  const load = () => {
    setLoading(true);
    productsAPI.get(productId).then((res) => setProduct(res.data)).finally(() => setLoading(false));
  };
  useEffect(() => { load(); }, [productId]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleActive = async () => {
    await productsAPI.update(product.id, { is_active: !product.is_active });
    load();
  };

  const confirmDelete = async () => {
    setError('');
    try {
      await productsAPI.remove(product.id);
      navigate('/products');
    } catch (err) {
      setError(err.response?.data?.detail || 'This product cannot be deleted - it has historical references. Deactivate it instead.');
      setPendingDelete(false);
    }
  };

  if (loading) return <div className="page"><p>Loading...</p></div>;
  if (!product) return <div className="page"><p>Product not found.</p></div>;

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/products" className="btn-link">&larr; Back to Products</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{product.name}</h1>
          <div className="detail-subtitle">
            {product.category || 'Uncategorized'}
            {product.business_id && <span className="business-id-badge">{product.business_id}</span>}
            <span className={`status-badge ${product.is_active ? 'status-ok' : 'status-muted'}`} style={{ marginLeft: 8 }}>
              {product.is_active ? 'Active' : 'Inactive'}
            </span>
          </div>
        </div>
        {isMaster && (
          <div className="page-actions">
            <button className="btn-secondary" onClick={toggleActive}>
              {product.is_active ? 'Deactivate' : 'Activate'}
            </button>
            <a className="btn-secondary" href={reportsAPI.downloadUrl(`products/${product.id}/product.pdf`)} target="_blank" rel="noreferrer">
              Export PDF
            </a>
            <a className="btn-secondary" href={reportsAPI.downloadUrl(`products.xlsx?search=${encodeURIComponent(product.product_code)}`)} target="_blank" rel="noreferrer">
              Export Excel
            </a>
            <button className="btn-link" onClick={() => setPendingDelete(true)}>Delete</button>
          </div>
        )}
      </div>

      {error && <p style={{ color: 'var(--danger)' }}>{error}</p>}

      <Card title="Product Information">
        <div className="detail-meta">
          <div className="detail-meta-item"><span className="detail-meta-label">Product ID</span><span className="detail-meta-value">{product.business_id || '-'}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Product Code</span><span className="detail-meta-value">{product.product_code}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Type</span><span className="detail-meta-value">{product.product_type}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Category</span><span className="detail-meta-value">{product.category || '-'}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Subcategory</span><span className="detail-meta-value">{product.subcategory || '-'}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Unit</span><span className="detail-meta-value">{product.unit}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Default Rate</span><span className="detail-meta-value">{product.selling_price != null ? formatCurrency(product.selling_price) : '-'}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">GST %</span><span className="detail-meta-value">{product.gst_percent != null ? `${product.gst_percent}%` : '-'}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Primary Material</span><span className="detail-meta-value">{product.primary_material || '-'}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Finish</span><span className="detail-meta-value">{product.finish || '-'}</span></div>
        </div>
        {product.specifications && (
          <div style={{ marginTop: 16 }}>
            <div className="detail-meta-label">Description / Specifications</div>
            <p>{product.specifications}</p>
          </div>
        )}
      </Card>

      {isMaster && (product.cost_price != null || product.margin != null) && (
        <Card title="Costing">
          <div className="detail-meta">
            <div className="detail-meta-item"><span className="detail-meta-label">Cost Price</span><span className="detail-meta-value">{product.cost_price != null ? formatCurrency(product.cost_price) : '-'}</span></div>
            <div className="detail-meta-item"><span className="detail-meta-label">Margin</span><span className="detail-meta-value">{product.margin != null ? formatCurrency(product.margin) : '-'}</span></div>
          </div>
        </Card>
      )}

      <Card title="System Information">
        <div className="detail-meta">
          <div className="detail-meta-item"><span className="detail-meta-label">Created</span><span className="detail-meta-value">{product.created_at ? new Date(product.created_at).toLocaleString() : '-'}</span></div>
          <div className="detail-meta-item"><span className="detail-meta-label">Last Updated</span><span className="detail-meta-value">{product.updated_at ? new Date(product.updated_at).toLocaleString() : '-'}</span></div>
        </div>
      </Card>

      <ConfirmDialog
        isOpen={pendingDelete}
        message={`Are you sure you want to permanently delete ${product.product_code} - ${product.name}? This cannot be undone.`}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(false)}
      />
    </div>
  );
}

export default ProductDetailPage;
