import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { businessDecisionsAPI } from '../../../utils/api';
import Card from '../../../components/common/Card';
import KpiCard from '../../../components/common/KpiCard';
import Alert from '../../../components/common/Alert';

const SEVERITY_TONE = { CRITICAL: 'danger', HIGH: 'warning', MEDIUM: 'default', LOW: 'default' };
const SEVERITY_BADGE_CLASS = {
  CRITICAL: 'status-badge status-danger', HIGH: 'status-badge status-warning',
  MEDIUM: 'status-badge status-neutral', LOW: 'status-badge status-neutral',
};

function BusinessDecisionCentrePage() {
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [filter, setFilter] = useState('ALL');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    setError('');
    businessDecisionsAPI.list().then((res) => setData(res.data)).catch((err) => {
      setError(err.response?.status === 403 ? 'You do not have permission to view business decisions.' : 'Unable to load business decisions right now.');
    }).finally(() => setLoading(false));
  };
  useEffect(load, []);

  if (loading) return <div className="page"><p>Loading...</p></div>;

  const risks = data?.risks || [];
  const filteredRisks = filter === 'ALL' ? risks : risks.filter((r) => r.severity === filter);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Business Attention</h1>
      </div>
      {error && <Alert type="error" message={error} onClose={() => setError('')} />}

      {data && (
        <div className="secondary-metrics" style={{ marginBottom: 'var(--space-5)' }}>
          <KpiCard label="Needs Attention" value={data.total} onClick={() => setFilter('ALL')} />
          <KpiCard label="Critical" value={data.counts.CRITICAL} tone="danger" onClick={() => setFilter('CRITICAL')} />
          <KpiCard label="High" value={data.counts.HIGH} tone="warning" onClick={() => setFilter('HIGH')} />
          <KpiCard label="Medium" value={data.counts.MEDIUM} onClick={() => setFilter('MEDIUM')} />
          <KpiCard label="Low" value={data.counts.LOW} onClick={() => setFilter('LOW')} />
        </div>
      )}

      <div className="page-actions" style={{ marginBottom: 'var(--space-4)' }}>
        {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((s) => (
          <button
            key={s} type="button"
            className={filter === s ? 'btn-primary' : 'btn-secondary'}
            onClick={() => setFilter(s)}
          >
            {s === 'ALL' ? 'All' : s.charAt(0) + s.slice(1).toLowerCase()}
          </button>
        ))}
      </div>

      {filteredRisks.length === 0 ? (
        <Card>
          <div className="card-body" style={{ color: 'var(--text-secondary)' }}>
            {risks.length === 0 ? 'Nothing needs attention right now.' : 'No items match this filter.'}
          </div>
        </Card>
      ) : (
        filteredRisks.map((risk) => (
          <Card key={`${risk.entity_type}-${risk.entity_id}-${risk.risk_type}`} style={{ marginBottom: 'var(--space-4)' }}>
            <div className="card-body">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 'var(--space-3)' }}>
                <div>
                  <span className={SEVERITY_BADGE_CLASS[risk.severity] || 'status-badge'}>{risk.severity}</span>
                  <span style={{ marginLeft: 'var(--space-2)', color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{risk.risk_type}</span>
                  <h3 style={{ marginTop: 'var(--space-2)', marginBottom: 0 }}>{risk.title}</h3>
                </div>
                {risk.action_path && (
                  <button type="button" className="btn-secondary" onClick={() => navigate(risk.action_path)}>
                    Review
                  </button>
                )}
              </div>
              <p style={{ marginTop: 'var(--space-3)' }}>{risk.reason}</p>
              {risk.business_impact && (
                <p style={{ color: 'var(--text-secondary)' }}><strong>Impact:</strong> {risk.business_impact}</p>
              )}
              {risk.recommended_action && (
                <p><strong>Recommended:</strong> {risk.recommended_action}</p>
              )}
            </div>
          </Card>
        ))
      )}
    </div>
  );
}

export default BusinessDecisionCentrePage;
