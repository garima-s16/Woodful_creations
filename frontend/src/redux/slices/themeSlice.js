import { createSlice } from '@reduxjs/toolkit';
import { THEME_STORAGE_KEY, resolveInitialTheme } from '../../utils/theme';

/* App-wide dark/light theme. Dark is the Woodful default for the
 * authenticated application (see styles/index.css) - the login page
 * instead follows the system/browser preference, per the standing
 * design decision that the login screen and the authenticated app have
 * distinct theme identities (see resolveInitialTheme). This slice only
 * tracks which one is active and persists an explicit user choice, the
 * same way chatUi/notificationUi track other cross-component UI state
 * that isn't worth a REST round-trip.
 *
 * Persisted directly to localStorage (read eagerly below, not via an
 * effect) so the very first paint already has the right value - an
 * effect-driven read would flash the wrong default before the effect
 * ran. */

const themeSlice = createSlice({
  name: 'theme',
  initialState: {
    mode: resolveInitialTheme(window.location.pathname),
  },
  reducers: {
    setTheme(state, action) {
      state.mode = action.payload === 'light' ? 'light' : 'dark';
      try {
        window.localStorage.setItem(THEME_STORAGE_KEY, state.mode);
      } catch {
        // Best-effort persistence only - theme still applies for this session.
      }
    },
    toggleTheme(state) {
      state.mode = state.mode === 'dark' ? 'light' : 'dark';
      try {
        window.localStorage.setItem(THEME_STORAGE_KEY, state.mode);
      } catch {
        // Best-effort persistence only - theme still applies for this session.
      }
    },
  },
});

export const { setTheme, toggleTheme } = themeSlice.actions;
export default themeSlice.reducer;
