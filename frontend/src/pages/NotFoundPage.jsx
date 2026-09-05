import React from 'react';
import { Link } from 'react-router-dom';

function NotFoundPage() {
  return (
    <div className="page" style={{ textAlign: 'center', paddingTop: 'var(--space-8, 4rem)' }}>
      <h1 style={{ fontSize: '4rem', margin: 0 }}>404</h1>
      <p style={{ fontSize: '1.2rem', color: 'var(--text-secondary)', marginTop: 'var(--space-2, 0.5rem)' }}>
        Page not found
      </p>
      <Link to="/" className="btn-primary" style={{ display: 'inline-block', marginTop: 'var(--space-4, 1.5rem)', textDecoration: 'none' }}>
        Back to Dashboard
      </Link>
    </div>
  );
}

export default NotFoundPage;
