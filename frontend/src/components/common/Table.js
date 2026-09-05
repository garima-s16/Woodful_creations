import React from 'react';
import './Table.css';

const Table = ({ columns, data, loading, error, onRetry, onRowClick, emptyMessage = 'No records yet.', emptyAction }) => {
  const alignStyle = (col) => (col.align ? { textAlign: col.align } : undefined);

  if (loading) {
    return (
      <div className="table-container">
        <table className="data-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key} scope="col" style={alignStyle(col)}>{col.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 5 }).map((_, rowIdx) => (
              <tr key={rowIdx} className="skeleton-row">
                {columns.map((col) => (
                  <td key={col.key}><span className="skeleton-bar" /></td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (error) {
    return (
      <div className="table-error">
        <p className="table-error-message">Unable to load this data. Please try again.</p>
        {onRetry && (
          <button type="button" className="btn-secondary table-error-retry" onClick={onRetry}>Retry</button>
        )}
      </div>
    );
  }

  if (!data || data.length === 0) {
    return (
      <div className="table-empty">
        <p className="table-empty-message">{emptyMessage}</p>
        {emptyAction && (
          <button type="button" className="btn-primary table-empty-action" onClick={emptyAction.onClick}>
            {emptyAction.label}
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="table-container">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key} scope="col" style={alignStyle(col)}>{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, index) => (
            <tr
              key={row.id || index}
              onClick={() => onRowClick && onRowClick(row)}
              onKeyDown={(e) => {
                if (onRowClick && (e.key === 'Enter' || e.key === ' ')) {
                  e.preventDefault();
                  onRowClick(row);
                }
              }}
              className={onRowClick ? 'clickable' : ''}
              tabIndex={onRowClick ? 0 : undefined}
              role={onRowClick ? 'button' : undefined}
            >
              {columns.map((col) => (
                <td key={`${row.id}-${col.key}`} style={alignStyle(col)}>
                  {col.render ? col.render(row[col.key], row) : row[col.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default Table;
