import React, { useState } from 'react';
import { useSelector } from 'react-redux';
import Card from '../components/common/Card';
import Alert from '../components/common/Alert';
import '../styles/components/MobileAppPage.css';

function MobileAppPage() {
  const { user } = useSelector((state) => state.auth);
  const [copied, setCopied] = useState(false);
  const [qrFailed, setQrFailed] = useState(false);

  // This page has no backend call of its own to enforce access through
  // (unlike most pages, which rely on the API's own RBAC check) - the
  // sidebar already hides this link from non-masters, but since there's
  // no server-side request here to also gate it, the check is made
  // directly rather than silently showing it to anyone who navigates
  // to the URL by hand.
  if (user?.role !== 'master') {
    return (
      <div className="page">
        <Alert type="error" message="This section is only available to master accounts." />
      </div>
    );
  }

  const appUrl = window.location.origin;
  const qrImageUrl = `https://api.qrserver.com/v1/create-qr-code/?size=280x280&margin=10&data=${encodeURIComponent(appUrl)}`;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(appUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API can fail (permissions, non-secure context) - the
      // URL is already shown as selectable text below regardless.
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>Get the Mobile App</h1>
          <p className="page-summary">
            Woodful Creations works as an installable app on both iPhone and Android, directly from
            the browser - no App Store or Play Store download required.
          </p>
        </div>
      </div>

      <div className="mobile-app-grid">
        <Card>
          <div className="card-body mobile-app-qr-card">
            <h3 style={{ marginTop: 0 }}>Scan to Open</h3>
            {!qrFailed ? (
              <img
                src={qrImageUrl} alt={`QR code linking to ${appUrl}`}
                className="mobile-app-qr-image" onError={() => setQrFailed(true)}
              />
            ) : (
              <div className="mobile-app-qr-fallback">
                Couldn't load the QR image. Use the link below instead.
              </div>
            )}
            <div className="mobile-app-url-row">
              <input type="text" readOnly value={appUrl} onFocus={(e) => e.target.select()} />
              <button className="btn-secondary" onClick={handleCopy}>{copied ? 'Copied!' : 'Copy Link'}</button>
            </div>
            <p className="mobile-app-qr-note">
              QR image generated via a public QR service (api.qrserver.com) from this page's own URL -
              nothing sensitive is encoded in it.
            </p>
          </div>
        </Card>

        <Card>
          <div className="card-body">
            <h3 style={{ marginTop: 0 }}>On iPhone (Safari)</h3>
            <ol className="mobile-app-steps">
              <li>Scan the code with the iPhone Camera app, or open the link above in Safari.</li>
              <li>Tap the Share button (the square with an arrow pointing up).</li>
              <li>Scroll down and tap <strong>Add to Home Screen</strong>.</li>
              <li>Tap <strong>Add</strong>. The Woodful icon now appears on the home screen like a regular app.</li>
            </ol>
            <p className="mobile-app-note">Must be opened in Safari - Add to Home Screen isn't available in Chrome or other browsers on iOS.</p>
          </div>
        </Card>

        <Card>
          <div className="card-body">
            <h3 style={{ marginTop: 0 }}>On Android (Chrome)</h3>
            <ol className="mobile-app-steps">
              <li>Scan the code with the Android Camera app, or open the link above in Chrome.</li>
              <li>Tap the menu (three dots, top right) or look for an "Install app" banner.</li>
              <li>Tap <strong>Install app</strong> (or <strong>Add to Home screen</strong>).</li>
              <li>Confirm. The Woodful icon now appears on the home screen and app drawer.</li>
            </ol>
          </div>
        </Card>
      </div>
    </div>
  );
}

export default MobileAppPage;
