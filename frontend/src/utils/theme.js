export const THEME_STORAGE_KEY = 'woodful-theme';

// Routes reachable before authentication - the only ones where theme
// should follow the system/browser preference rather than Woodful's
// own dark default. Kept in sync with App.jsx's own <Route path="...">
// list for these three pages (not derived from it programmatically,
// since this module must be importable and run before React Router
// itself initializes).
const UNAUTHENTICATED_PATHS = ['/login', '/forgot-password', '/reset-password'];

function systemPrefersLight() {
  try {
    return window.matchMedia('(prefers-color-scheme: light)').matches;
  } catch {
    // matchMedia unavailable (very old browser, or a test/SSR
    // environment) - Woodful's own dark default applies instead of
    // guessing at a system preference that can't be read.
    return false;
  }
}

/* Resolves which theme should be active on this exact page load.
 *
 * - An explicit, previously-saved user choice (from either the login
 *   page's own system-following default or a manual switch inside the
 *   authenticated app) always wins, on every route - a user who chose
 *   light once should keep seeing light everywhere, not have it
 *   silently overridden by whichever page they're on.
 * - With no saved choice yet: the login/forgot-password/reset-password
 *   pages follow the system/browser preference (never forced to dark);
 *   every other (authenticated) page defaults to Woodful's own dark
 *   theme regardless of system preference, per the standing design
 *   decision that the authenticated application has its own identity,
 *   distinct from the login screen.
 */
export function resolveInitialTheme(pathname) {
  let stored = null;
  try {
    stored = window.localStorage.getItem(THEME_STORAGE_KEY);
  } catch {
    // localStorage unavailable (private browsing, disabled storage) -
    // fall through to the route-based default below.
  }
  if (stored === 'light' || stored === 'dark') return stored;

  if (UNAUTHENTICATED_PATHS.includes(pathname)) {
    return systemPrefersLight() ? 'light' : 'dark';
  }
  return 'dark';
}
