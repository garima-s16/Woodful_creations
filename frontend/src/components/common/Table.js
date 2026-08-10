import React from 'react';
import './Table.css';

const Table = ({ columns, data, loading, error, onRowClick, emptyMessage = 'No records yet.' }) => {
  if (loading) {
    return <div className="table-loading">Loading...</div>;
  }

  if (error) {
    return <div className="table-error">Unable to load this data. Please try again.</div>;
  }

  if (!data || data.length === 0) {
    return <div className="table-empty">{emptyMessage}</div>;
  }

  return (
    <div className="table-container">
      <table className="data-table">
        <thead>
          <tr>
            {columns.map((col) => (
              <th key={col.key}>{col.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, index) => (
            <tr
              key={row.id || index}
              onClick={() => onRowClick && onRowClick(row)}
              className={onRowClick ? 'clickable' : ''}
            >
              {columns.map((col) => (
                <td key={`${row.id}-${col.key}`}>
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
