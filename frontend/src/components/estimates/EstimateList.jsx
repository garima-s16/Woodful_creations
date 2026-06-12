import React from 'react';
import '../../styles/components/estimates/EstimateList.css';

function EstimateList({ estimates, selectedEstimate, onSelectEstimate, onGeneratePDF }) {
  return (
    <div className="estimate-list">
      {estimates.length > 0 ? (
        <ul className="estimate-items">
          {estimates.map(estimate => (
            <li 
              key={estimate.id}
              className={`estimate-item ${selectedEstimate?.id === estimate.id ? 'selected' : ''}`}
              onClick={() => onSelectEstimate(estimate)}
            >
              <div className="estimate-header">
                <div className="estimate-number">EST-{estimate.id}</div>
                <div className="estimate-status">
                  <span className={`status-badge ${estimate.status}`}>
                    {estimate.status.charAt(0).toUpperCase() + estimate.status.slice(1)}
                  </span>
                </div>
              </div>
              <div className="estimate-info">
                <span className="client-name">{estimate.client_name}</span>
                <span className="estimate-date">{estimate.created_date}</span>
              </div>
              <div className="estimate-amount">
                Rs {estimate.total_amount}
              </div>
              <button 
                className="btn-pdf"
                onClick={(e) => {
                  e.stopPropagation();
                  onGeneratePDF(estimate.id);
                }}
              >
                PDF
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <div className="no-estimates">No estimates found</div>
      )}
    </div>
  );
}

export default EstimateList;