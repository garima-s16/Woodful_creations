import React from 'react';
import '../styles/components/Footer.css';

function Footer() {
  const year = new Date().getFullYear();

  return (
    <footer className="app-footer">
      <div className="app-footer-inner">
        <p>&copy; {year} Woodful Creations. All rights reserved.</p>
      </div>
    </footer>
  );
}

export default Footer;
