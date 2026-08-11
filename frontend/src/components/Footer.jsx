import React from 'react';
import '../styles/components/Footer.css';

function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="app-footer">
      <div className="app-footer-inner">
        <div className="app-footer-brand">
          <img src="/logo.png" alt="Woodful Creations" className="app-footer-logo" />
        </div>
        <div className="app-footer-meta">
          <p>&copy; {year} Woodful Creations. All rights reserved.</p>
          <p>Founded by Nikhil Soni.</p>
        </div>
      </div>
    </footer>
  );
}

export default Footer;
