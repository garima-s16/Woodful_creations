// Registers public/service-worker.js, which lets the app work offline
// and be installed to an iPhone's home screen via Safari's "Add to Home
// Screen" (the manifest.json + apple-touch-icon handle the icon/name;
// this is what makes the installed app actually load without a network
// connection for pages it's already cached).
//
// Only registers in production builds and only over HTTPS/localhost -
// service workers require a secure context, and registering one during
// local development would cache stale JS while iterating.

const isLocalhost = Boolean(
  window.location.hostname === 'localhost' ||
    window.location.hostname === '127.0.0.1' ||
    window.location.hostname === '[::1]'
);

export function register() {
  if (process.env.NODE_ENV !== 'production') return;
  if (!('serviceWorker' in navigator)) return;

  window.addEventListener('load', () => {
    const swUrl = `${process.env.PUBLIC_URL}/service-worker.js`;
    if (isLocalhost) {
      // Still register on localhost (useful for testing the production
      // build locally via `serve -s build`), but check it's actually
      // reachable first so a misconfigured PUBLIC_URL fails clearly.
      checkValidServiceWorker(swUrl);
    } else {
      navigator.serviceWorker.register(swUrl).catch((error) => {
        // eslint-disable-next-line no-console
        console.error('Service worker registration failed:', error);
      });
    }
  });
}

function checkValidServiceWorker(swUrl) {
  fetch(swUrl, { headers: { 'Service-Worker': 'script' } })
    .then((response) => {
      const contentType = response.headers.get('content-type');
      if (response.status === 404 || (contentType != null && contentType.indexOf('javascript') === -1)) {
        // No real service worker found - don't register anything.
        return;
      }
      navigator.serviceWorker.register(swUrl).catch((error) => {
        // eslint-disable-next-line no-console
        console.error('Service worker registration failed:', error);
      });
    })
    .catch(() => {
      // eslint-disable-next-line no-console
      console.log('No internet connection - app running in offline mode.');
    });
}

export function unregister() {
  if (!('serviceWorker' in navigator)) return;
  navigator.serviceWorker.ready
    .then((registration) => registration.unregister())
    .catch((error) => {
      // eslint-disable-next-line no-console
      console.error(error.message);
    });
}
