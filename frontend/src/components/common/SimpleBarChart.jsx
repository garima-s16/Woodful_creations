import React from 'react';
import '../../styles/components/SimpleBarChart.css';

/* A small, dependency-free horizontal bar chart, built with plain CSS
 * width percentages (no SVG, no charting library needed - none exists
 * in this project, and a new npm dependency couldn't be verified to
 * resolve correctly in this environment) - driven entirely by real
 * data passed in. */
function SimpleBarChart({ data, labelKey, valueKey, formatValue = (v) => v, color = 'var(--color-gold)' }) {
  if (!data || data.length === 0) {
    return <div className="simple-chart-empty">No data yet.</div>;
  }
  const max = Math.max(...data.map((d) => Number(d[valueKey]) || 0), 1);

  return (
    <div className="simple-bar-chart">
      {data.map((d, i) => {
        const value = Number(d[valueKey]) || 0;
        const pct = (value / max) * 100;
        return (
          <div className="simple-bar-row" key={i}>
            <span className="simple-bar-label">{d[labelKey]}</span>
            <div className="simple-bar-track">
              <div className="simple-bar-fill" style={{ width: `${pct}%`, background: color }} />
            </div>
            <span className="simple-bar-value">{formatValue(value)}</span>
          </div>
        );
      })}
    </div>
  );
}

export default SimpleBarChart;
