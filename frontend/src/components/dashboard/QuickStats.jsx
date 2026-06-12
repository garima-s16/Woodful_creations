import React from 'react';
import '../../styles/components/dashboard/QuickStats.css';

function QuickStats({ data }) {
  const stats = data || [
    { label: 'Total Products', value: '0', change: '+0%' },
    { label: 'Low Stock Items', value: '0', change: '+0%' },
    { label: 'Pending Orders', value: '0', change: '+0%' },
    { label: 'Total Clients', value: '0', change: '+0%' },
  ];

  return (
    <div className="quick-stats">
      <h2>Quick Statistics</h2>
      <div className="stats-grid">
        {stats.map((stat, index) => (
          <div key={index} className="stat-card">
            <div className="stat-label">{stat.label}</div>
            <div className="stat-value">{stat.value}</div>
            <div className="stat-change">{stat.change}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default QuickStats;