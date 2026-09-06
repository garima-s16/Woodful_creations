import React from 'react';
import Card from './Card';
import './KpiCard.css';

function KpiCard({ label, value, tone = 'default', onClick }) {
  return (
    <Card
      className={`kpi-card kpi-${tone}${onClick ? ' kpi-card-clickable' : ''}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') onClick(); } : undefined}
    >
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
    </Card>
  );
}

export default KpiCard;
