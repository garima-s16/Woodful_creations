import React, { useEffect, useState, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { procurementRequirementsAPI, purchasesAPI } from '../../../utils/api';
import Card from '../../../components/common/Card';
import Form from '../../../components/common/Form';
import Alert from '../../../components/common/Alert';
import { statusClass } from '../../../utils/format';

function ProcurementRequirementDetailPage() {
  const { requirementId } = useParams();
  const [requirement, setRequirement] = useState(null);
  const [options, setOptions] = useState(null);
  const [purchase, setPurchase] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [pageLoading, setPageLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  const load = useCallback(() => {
    setPageLoading(true);
    setLoadError(false);
    procurementRequirementsAPI.get(requirementId).then((res) => {
      setRequirement(res.data);
    }).catch((err) => {
      setLoadError(true);
      setError(err.response?.status === 403 ? 'You do not have permission to view this requirement.' : 'Unable to load this requirement.');
    }).finally(() => setPageLoading(false));
  }, [requirementId]);

  useEffect(load, [load]);

  useEffect(() => {
    if (requirement && !requirement.decision && requirement.status === 'Open') {
      procurementRequirementsAPI.supplierOptions(requirementId).then((res) => setOptions(res.data.options)).catch(() => setOptions([]));
    }
  }, [requirement, requirementId]);

  useEffect(() => {
    if (requirement?.purchase_id) {
      purchasesAPI.get(requirement.purchase_id).then((res) => setPurchase(res.data)).catch(() => setPurchase(null));
    }
  }, [requirement]);

  const handleDecision = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await procurementRequirementsAPI.recordDecision(requirementId, {
        requirement_id: Number(requirementId), selected_supplier_id: Number(formData.selected_supplier_id),
        decision_reason: formData.decision_reason,
      });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to record the supplier decision.');
    } finally {
      setLoading(false);
    }
  };

  const handlePurchase = async (formData) => {
    setLoading(true);
    setError('');
    try {
      await procurementRequirementsAPI.createPurchase(requirementId, {
        ...formData, quantity: formData.quantity, rate: formData.rate,
        gst_percent: formData.gst_percent || '18',
      });
      load();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create the purchase.');
    } finally {
      setLoading(false);
    }
  };

  if (pageLoading) return <div className="page"><p>Loading...</p></div>;
  if (loadError || !requirement) return <div className="page">{error && <Alert type="error" message={error} />}</div>;

  const decisionFields = [
    { name: 'selected_supplier_id', label: 'Selected Supplier', type: 'select', required: true,
      options: (options || []).map((o) => ({ value: o.supplier_id, label: `${o.supplier_name}${o.is_preferred ? ' (Preferred)' : ''}${o.price != null ? ` - ₹${o.price}` : ''}` })) },
    { name: 'decision_reason', label: 'Reason', type: 'textarea', placeholder: 'Why this supplier, if it diverges from the recommendation' },
  ];

  const purchaseFields = [
    { name: 'quantity', label: 'Quantity', type: 'number', required: true },
    { name: 'unit', label: 'Unit', required: true, placeholder: requirement.material_name ? '' : 'e.g. Sheets' },
    { name: 'rate', label: 'Rate', type: 'number', required: true },
    { name: 'gst_percent', label: 'GST %', type: 'number', placeholder: '18' },
    { name: 'expected_delivery_date', label: 'Expected Delivery', type: 'date' },
    { name: 'receipt_status', label: 'Receipt Status', type: 'select', options: [
      { value: 'Ordered', label: 'Ordered (not yet in hand)' }, { value: 'Received', label: 'Received (already in hand)' },
    ] },
  ];

  return (
    <div className="page">
      <div className="page-header">
        <h1>{requirement.material_name}</h1>
        <span className={statusClass(requirement.status)}>{requirement.status}</span>
      </div>
      {error && <Alert type="error" message={error} />}

      <Card title="Why this requirement exists">
        <div className="detail-grid">
          <div><div className="detail-meta-label">Required</div><h3>{requirement.required_quantity}</h3></div>
          <div><div className="detail-meta-label">Available (at creation)</div><h3>{requirement.available_quantity_at_creation}</h3></div>
          <div><div className="detail-meta-label">Shortage (at creation)</div><h3>{requirement.shortage_quantity_at_creation}</h3></div>
          <div><div className="detail-meta-label">Priority</div><h3>{requirement.priority || '-'}</h3></div>
        </div>
        {requirement.order_id && <p><Link to={`/orders/${requirement.order_id}`}>View the related order</Link></p>}
        {requirement.remarks && <p>{requirement.remarks}</p>}
      </Card>

      {!requirement.decision && requirement.status === 'Open' && (
        <Card title="Supplier Options">
          {options === null ? <p>Loading supplier options...</p> : options.length === 0 ? (
            <Alert type="info" message="No supplier is linked to this material yet - add a SupplierMaterial relationship first." />
          ) : (
            <>
              <ul>
                {options.map((o) => (
                  <li key={o.supplier_id}>
                    {o.supplier_name}{o.is_preferred ? ' - Preferred' : ''}{o.price != null ? ` - ₹${o.price}` : ' - no price on file'}
                    {o.lead_time_days != null ? `, ${o.lead_time_days}d lead time` : ''}
                  </li>
                ))}
              </ul>
              <Form fields={decisionFields} onSubmit={handleDecision} loading={loading} submitText="Record Supplier Decision" />
            </>
          )}
        </Card>
      )}

      {requirement.decision && (
        <Card title="Supplier Decision">
          <div className="detail-grid">
            <div><div className="detail-meta-label">Recommended</div><h3>{requirement.decision.recommended_supplier_name || 'None'}</h3></div>
            <div><div className="detail-meta-label">Selected</div><h3>{requirement.decision.selected_supplier_name}</h3></div>
            <div><div className="detail-meta-label">Followed Recommendation</div><h3>{requirement.decision.followed_recommendation === null ? 'N/A' : requirement.decision.followed_recommendation ? 'Yes' : 'No'}</h3></div>
          </div>
          {requirement.decision.decision_reason && <p>{requirement.decision.decision_reason}</p>}
        </Card>
      )}

      {requirement.decision && !requirement.purchase_id && (
        <Card title="Create Purchase">
          <Form fields={purchaseFields} onSubmit={handlePurchase} loading={loading} submitText="Create Purchase" />
        </Card>
      )}

      {purchase && (
        <Card title="Resulting Purchase">
          <div className="detail-grid">
            <div><div className="detail-meta-label">Purchase</div><h3><Link to={`/purchases/${purchase.id}`}>{purchase.purchase_code}</Link></h3></div>
            <div><div className="detail-meta-label">Receipt Status</div><h3>{purchase.receipt_status}</h3></div>
          </div>
        </Card>
      )}
    </div>
  );
}

export default ProcurementRequirementDetailPage;
