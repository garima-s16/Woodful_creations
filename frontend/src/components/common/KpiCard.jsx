import React from 'react';
import Card from './Card';
import './KpiCard.css';

function KpiCard({ label, value, tone = 'default' }) {
  return (
    <Card className={`kpi-card kpi-${tone}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
    </Card>
  );
}

export default KpiCard;
