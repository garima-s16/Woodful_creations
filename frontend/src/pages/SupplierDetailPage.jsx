import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useSelector } from 'react-redux';
import { suppliersAPI, purchasesAPI } from '../utils/api';
import Table from '../components/common/Table';
import Card from '../components/common/Card';
import { formatCurrency } from '../utils/currency';


function SupplierDetailPage() {
  const { supplierId } = useParams();
  const { user } = useSelector((state) => state.auth);
  const isPrivileged = user?.role === 'master';
  const [supplier, setSupplier] = useState(null);
  const [purchases, setPurchases] = useState([]);

  const load = useCallback(() => {
    suppliersAPI.get(supplierId).then((res) => setSupplier(res.data)).catch(() => setSupplier(null));
    purchasesAPI.list({ supplier_id: supplierId }).then((res) => setPurchases(res.data)).catch(() => setPurchases([]));
  }, [supplierId]);

  useEffect(load, [load]);

  if (!supplier) return <div className="page">Loading...</div>;

  const totalPurchased = purchases.reduce((sum, p) => sum + Number(p.invoice_total || 0), 0);
  const outstanding = purchases.filter((p) => p.payment_status !== 'Paid');

  return (
    <div className="page">
      <div className="detail-header">
        <div>
          <Link to="/suppliers" className="btn-link">&larr; Back to Suppliers</Link>
          <h1 className="detail-title" style={{ marginTop: 8 }}>{supplier.name}</h1>
          <div className="detail-subtitle">
            {supplier.supplier_code} &middot; {supplier.category || 'Uncategorized'}
            {supplier.business_id && <span className="business-id-badge">{supplier.business_id}</span>}
          </div>
        </div>
      </div>

      <div className="kpi-row">
        {isPrivileged && (
          <>
            <Card><div className="card-body"><div className="detail-meta-label">Total Purchased</div><h3>{formatCurrency(totalPurchased)}</h3></div></Card>
            <Card><div className="card-body"><div className="detail-meta-label">Purchase Count</div><h3>{purchases.length}</h3></div></Card>
            <Card><div className="card-body"><div className="detail-meta-label">Unpaid/Part Paid Invoices</div><h3>{outstanding.length}</h3></div></Card>
          </>
        )}
        <Card><div className="card-body"><div className="detail-meta-label">Payment Terms</div><h3 style={{ fontSize: '1.1rem' }}>{supplier.payment_terms || '-'}</h3></div></Card>
      </div>

      <Card title="Supplier Details">
        <div className="card-body">
          <div className="detail-meta">
            <div className="detail-meta-item"><span className="detail-meta-label">Contact Person</span><span className="detail-meta-value">{supplier.contact_person || '-'}</span></div>
            <div className="detail-meta-item"><span className="detail-meta-label">Phone</span><span className="detail-meta-value">{supplier.phone || '-'}</span></div>
            <div className="detail-meta-item"><span className="detail-meta-label">GSTIN</span><span className="detail-meta-value">{supplier.gstin || '-'}</span></div>
          </div>
        </div>
      </Card>

      {isPrivileged && (
        <Card title="Purchase History">
          <Table
            columns={[
              { key: 'purchase_code', label: 'Purchase' },
              { key: 'date', label: 'Date', render: (v) => new Date(v).toLocaleDateString() },
              { key: 'quantity', label: 'Quantity' }, { key: 'invoice_total', label: 'Invoice Total', render: formatCurrency },
              { key: 'payment_status', label: 'Payment Status' },
            ]}
            data={purchases}
            emptyMessage="No purchases recorded from this supplier yet."
          />
        </Card>
      )}
    </div>
  );
}

export default SupplierDetailPage;
