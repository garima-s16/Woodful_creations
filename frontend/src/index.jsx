import React from 'react';
import ReactDOM from 'react-dom/client';
import { Provider } from 'react-redux';
import App from './App';
import store from './redux/store';
import * as serviceWorkerRegistration from './serviceWorkerRegistration';
import './styles/index.css';
import './styles/modules.css';
import { resolveInitialTheme } from './utils/utils';

// Applied synchronously, before the first paint, so there's never a
// flash of the wrong theme while React mounts and its own effects run.
// themeSlice's initial state uses the same resolveInitialTheme helper,
// so this and the redux store agree from the first render. See
// utils/utils.js for the full login-vs-authenticated-app rule.
try {
  const theme = resolveInitialTheme(window.location.pathname);
  if (theme === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
  }
} catch {
  // Theme resolution unavailable for some reason - app stays on the
  // dark default rather than breaking the page load over this.
}

// Defense in depth: most pages fire several "list" API calls per load
// (e.g. `materialsAPI.list().then(...)`) without an individual .catch,
// since a failed secondary fetch there just means an empty dropdown, not
// a broken page. If the backend is unreachable, every one of those
// rejects at once. Left unhandled, that trips CRA's dev-mode error
// overlay for what is really just "the API is down right now" - a
// recoverable, expected condition - not a code bug that should block the
// whole UI. Swallow ONLY genuine network-level failures (no response
// received at all) here; anything that reached the server and came back
// as a real error still surfaces normally so actual bugs aren't hidden.
window.addEventListener('unhandledrejection', (event) => {
  const err = event.reason;
  const isNetworkError = err?.isAxiosError && !err.response;
  if (isNetworkError) {
    // eslint-disable-next-line no-console
    console.error('API request failed (backend unreachable):', err.config?.url || err.message);
    event.preventDefault();
  }
});

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <Provider store={store}>
      <App />
    </Provider>
  </React.StrictMode>
);

serviceWorkerRegistration.register();