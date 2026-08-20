import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { productsAPI, documentsAPI } from '../utils/api';
import Card from '../components/common/Card';
import DocumentsPanel from '../components/DocumentsPanel';
import { formatCurrency } from '../utils/currency';

function ProductDetailPage() {
  const { productId } = useParams();
  const navigate = useNavigate();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [product, setProduct] = useState(null);
  const [notFound, setNotFound] = useState(false);

  const load = useCallback(() => {
    productsAPI.get(productId).then((res) => setProduct(res.data)).catch(() => setNotFound(true));
  }, [productId]);

  useEffect(load, [load]);

  if (notFound) return <div className="page"><p>Product not found.</p></div>;
  if (!product) return <div className="page">Loading...</div>;

  const dims = [product.length, product.width, product.height].filter((d) => d != null);

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/products" className="btn-link">&larr; Back to Product Master</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{product.name}</h1>
          <div className="detail-subtitle">
            {product.product_code} &middot; {product.product_type === 'custom' ? 'Custom' : 'Standard'}
            {product.category ? ` · ${product.category}` : ''}
            {' '}<span className={`status-badge ${product.is_active ? 'status-ok' : 'status-muted'}`}>{product.is_active ? 'Active' : 'Inactive'}</span>
            {product.business_id && <span className="business-id-badge">{product.business_id}</span>}
          </div>
        </div>
        {isPrivileged && (
          <div className="detail-header-actions">
            <button className="btn-secondary" onClick={() => navigate('/products', { state: { openEditId: product.id } })}>
              Manage in Product Master
            </button>
          </div>
        )}
      </div>

      <div className="kpi-row">
        <Card><div className="card-body"><div className="detail-meta-label">Selling Price</div><h3>{formatCurrency(product.selling_price)}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Cost Price</div><h3>{product.cost_price != null ? formatCurrency(product.cost_price) : 'Restricted'}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Margin</div><h3>{product.margin != null ? formatCurrency(product.margin) : 'Restricted'}</h3></div></Card>
        <Card><div className="card-body"><div className="detail-meta-label">Lead Time</div><h3>{product.lead_time_days ? `${product.lead_time_days} days` : '-'}</h3></div></Card>
      </div>

      <Card title="Details">
        <div className="card-body">
          <div className="detail-meta">
            <div className="detail-meta-item"><span className="detail-meta-label">SKU</span><span className="detail-meta-value">{product.sku || '-'}</span></div>
            <div className="detail-meta-item"><span className="detail-meta-label">Unit</span><span className="detail-meta-value">{product.unit}</span></div>
            <div className="detail-meta-item"><span className="detail-meta-label">Finish</span><span className="detail-meta-value">{product.finish || '-'}</span></div>
            <div className="detail-meta-item">
              <span className="detail-meta-label">Dimensions</span>
              <span className="detail-meta-value">
                {dims.length > 0 ? `${dims.join(' x ')} ${product.dimension_unit}` : '-'}
              </span>
            </div>
            <div className="detail-meta-item"><span className="detail-meta-label">Tax %</span><span className="detail-meta-value">{Number(product.tax_percent)}%</span></div>
          </div>
          {product.description && (
            <div style={{ marginTop: 16 }}>
              <span className="detail-meta-label">Description</span>
              <p>{product.description}</p>
            </div>
          )}
          {product.specifications && (
            <div style={{ marginTop: 16 }}>
              <span className="detail-meta-label">Specifications</span>
              <p>{product.specifications}</p>
            </div>
          )}
          {product.notes && (
            <div style={{ marginTop: 16 }}>
              <span className="detail-meta-label">Notes</span>
              <p>{product.notes}</p>
            </div>
          )}
        </div>
      </Card>

      {product.bom_items?.length > 0 && (
        <Card title="Bill of Materials">
          <table className="data-table">
            <thead><tr><th>Material</th><th>Quantity</th><th>Unit</th></tr></thead>
            <tbody>
              {product.bom_items.map((b) => (
                <tr key={b.id}>
                  <td><Link to={`/materials/${b.material_id}`} className="btn-link">{b.material_name}</Link></td>
                  <td>{Number(b.quantity)}</td>
                  <td>{b.unit || b.material_unit}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}

      <DocumentsPanel title="Reference Images & Attachments" api={{
        list: () => documentsAPI.list('product', productId),
        upload: (file, description) => documentsAPI.upload('product', productId, file, description),
        downloadUrl: (documentId) => documentsAPI.downloadUrl('product', productId, documentId),
        remove: (documentId) => documentsAPI.remove('product', productId, documentId),
      }} canUpload={isPrivileged} />
    </div>
  );
}

export default ProductDetailPage;
