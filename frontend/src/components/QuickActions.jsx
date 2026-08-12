import React from 'react';
import { useNavigate } from 'react-router-dom';
import '../styles/components/QuickActions.css';

const ACTIONS = [
  { label: 'New Client', path: '/clients' },
  { label: 'New Estimate', path: '/estimates' },
  { label: 'New Order', path: '/orders' },
  { label: 'Record Payment', path: '/payments' },
  { label: 'Add Material', path: '/materials' },
  { label: 'Create Purchase', path: '/purchases' },
  { label: 'Assign Task', path: '/daily-tasks' },
  { label: 'Create Production Job', path: '/production-jobs' },
];

function QuickActions() {
  const navigate = useNavigate();

  return (
    <div className="quick-actions">
      {ACTIONS.map((action) => (
        <button
          key={action.path}
          className="quick-action-btn"
          onClick={() => navigate(action.path, { state: { openCreate: true } })}
        >
          <span className="quick-action-plus">+</span>
          {action.label}
        </button>
      ))}
    </div>
  );
}

export default QuickActions;
