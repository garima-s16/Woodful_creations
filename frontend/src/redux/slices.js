// All Redux slices: auth, cart, chat UI, notification UI, theme.
// Combines the former authSlice.js, cartSlice.js, chatUiSlice.js,
// notificationUiSlice.js, and themeSlice.js.

import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { materialsAPI, personalCartAPI } from '../utils/api';
import { THEME_STORAGE_KEY, resolveInitialTheme } from '../utils/utils';

// --- authSlice.js ---
const authSlice = createSlice({
  name: 'auth',
  initialState: {
    user: null,
    isAuthenticated: false,
    // true until the initial /api/auth/me check completes, so ProtectedRoute
    // doesn't redirect to /login before we know the cookie is valid.
    checkingSession: true,
    // Distinct from "not logged in" (a normal, expected 401): this
    // means the request never reached the server at all, so
    // ProtectedRoute can show a real "can't connect" message instead
    // of silently sending someone to the login page with no
    // explanation of why they got logged out.
    connectionError: false,
    loading: false,
    error: null,
  },
  reducers: {
    loginStart: (state) => {
      state.loading = true;
      state.error = null;
    },
    loginSuccess: (state, action) => {
      state.loading = false;
      state.isAuthenticated = true;
      state.checkingSession = false;
      state.connectionError = false;
      state.user = action.payload.user;
      state.error = null;
    },
    loginFailure: (state, action) => {
      state.loading = false;
      state.isAuthenticated = false;
      state.checkingSession = false;
      state.error = action.payload;
    },
    sessionCheckFinished: (state, action) => {
      state.checkingSession = false;
      state.connectionError = false;
      if (action.payload) {
        state.isAuthenticated = true;
        state.user = action.payload;
      } else {
        state.isAuthenticated = false;
        state.user = null;
      }
    },
    sessionCheckFailed: (state) => {
      // The initial session check never reached the server (network
      // error/timeout) - not the same as "checked and you're not
      // logged in". Leaves isAuthenticated/user untouched (both
      // already default to false/null) since we genuinely don't know
      // either way; connectionError is what ProtectedRoute keys off.
      state.checkingSession = false;
      state.connectionError = true;
    },
    logout: (state) => {
      state.isAuthenticated = false;
      state.user = null;
      state.error = null;
    },
    clearError: (state) => {
      state.error = null;
    },
  },
});

export const {
  loginStart,
  loginSuccess,
  loginFailure,
  sessionCheckFinished,
  sessionCheckFailed,
  logout,
  clearError,
} = authSlice.actions;

export const authReducer = authSlice.reducer;

// --- cartSlice.js ---
/**
 * Purchase Cart - lets a user build up a "to purchase" list while
 * browsing the Material Catalog, the same way an e-commerce cart works.
 *
 * The database (personal_cart_items, via personalCartAPI) is the
 * authoritative source of truth - Redux is only a UI cache populated by
 * fetching from the API, never localStorage. This is what makes the
 * cart genuinely survive logout/login/browser restart, and what makes
 * it correctly isolated per user (the backend scopes every query to the
 * authenticated user's own id - see personal_cart.py - so there is no
 * client-side key to get wrong).
 *
 * Adding an item here does NOT touch inventory, does NOT create a
 * Purchase, and does NOT affect any other user's cart - it is purely a
 * personal request list until explicitly sent to procurement.
 */

function mapItem(apiItem, currentStock) {
  return {
    id: apiItem.id, // real database id, needed for update/remove calls
    materialId: apiItem.material_id,
    name: apiItem.material_name,
    unit: apiItem.unit,
    rate: apiItem.rate != null ? Number(apiItem.rate) : 0,
    supplierId: apiItem.supplier_id,
    supplierName: apiItem.supplier_name,
    quantity: Number(apiItem.quantity),
    currentStock: currentStock ?? null,
  };
}

// Fetches the current user's cart, then enriches each line with live
// stock (not part of the cart record itself - the cart snapshots the
// material's name/rate at add-time, but stock changes constantly and
// must always be current for the shortage math in CartDrawer).
export const fetchCart = createAsyncThunk('cart/fetchCart', async () => {
  const res = await personalCartAPI.list();
  const items = res.data;
  const stockLookups = await Promise.all(
    items.map((item) =>
      materialsAPI.get(item.material_id).then((r) => r.data.current_stock).catch(() => null)
    )
  );
  return items.map((item, i) => mapItem(item, stockLookups[i]));
});

export const addToCart = createAsyncThunk('cart/addToCart', async (payload) => {
  const res = await personalCartAPI.add({
    material_id: payload.materialId,
    quantity: payload.quantity,
    supplier_id: payload.supplierId || undefined,
  });
  return mapItem(res.data, payload.currentStock);
});

export const updateQuantity = createAsyncThunk(
  'cart/updateQuantity',
  async ({ materialId, quantity }, { getState }) => {
    const existing = getState().cart.items.find((i) => i.materialId === materialId);
    if (!existing) return null;
    if (quantity <= 0) {
      await personalCartAPI.remove(existing.id);
      return { removedMaterialId: materialId };
    }
    const res = await personalCartAPI.update(existing.id, { quantity });
    return { updated: mapItem(res.data, existing.currentStock) };
  }
);

export const removeFromCart = createAsyncThunk(
  'cart/removeFromCart',
  async (materialId, { getState }) => {
    const existing = getState().cart.items.find((i) => i.materialId === materialId);
    if (existing) await personalCartAPI.remove(existing.id);
    return materialId;
  }
);

export const clearCart = createAsyncThunk('cart/clearCart', async () => {
  await personalCartAPI.clear();
});

const cartSlice = createSlice({
  name: 'cart',
  initialState: {
    items: [],
    loaded: false,
    // Not persisted - the single source of truth for whether the
    // drawer is open, so both App.jsx (which renders it) and
    // ChatWidget (which needs to know for cart-aware suggestions) read
    // the same value instead of App.jsx keeping its own separate,
    // invisible-to-chat state.
    isOpen: false,
  },
  reducers: {
    openCart(state) {
      state.isOpen = true;
    },
    closeCart(state) {
      state.isOpen = false;
    },
    // Called on logout - clears the in-memory view only. Nothing is
    // deleted from the database; the same user logging back in will
    // fetchCart() again and see everything exactly as they left it.
    resetCartView(state) {
      state.items = [];
      state.loaded = false;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchCart.fulfilled, (state, action) => {
        state.items = action.payload;
        state.loaded = true;
      })
      .addCase(addToCart.fulfilled, (state, action) => {
        const idx = state.items.findIndex((i) => i.materialId === action.payload.materialId);
        if (idx >= 0) state.items[idx] = action.payload;
        else state.items.push(action.payload);
      })
      .addCase(updateQuantity.fulfilled, (state, action) => {
        if (!action.payload) return;
        if (action.payload.removedMaterialId != null) {
          state.items = state.items.filter((i) => i.materialId !== action.payload.removedMaterialId);
        } else if (action.payload.updated) {
          const idx = state.items.findIndex((i) => i.materialId === action.payload.updated.materialId);
          if (idx >= 0) state.items[idx] = action.payload.updated;
        }
      })
      .addCase(removeFromCart.fulfilled, (state, action) => {
        state.items = state.items.filter((i) => i.materialId !== action.payload);
      })
      .addCase(clearCart.fulfilled, (state) => {
        state.items = [];
      });
  },
});

export const { openCart, closeCart, resetCartView } = cartSlice.actions;
export const cartReducer = cartSlice.reducer;

// --- chatUiSlice.js ---
/* Coordinates the top command bar (Navbar) with the actual chat panel
 * (ChatWidget) - they're siblings, not parent/child, so a plain prop
 * can't connect them. When the command bar is submitted, it dispatches
 * openWithMessage(text); ChatWidget watches pendingMessage, opens
 * itself, sends that text through its own real send() flow (so it
 * goes through the exact same backend/propose-confirm logic as typing
 * directly into the panel - no separate code path), then clears it. */
const chatUiSlice = createSlice({
  name: 'chatUi',
  initialState: {
    pendingMessage: null,
  },
  reducers: {
    openWithMessage(state, action) {
      state.pendingMessage = action.payload;
    },
    clearPendingMessage(state) {
      state.pendingMessage = null;
    },
  },
});

export const { openWithMessage, clearPendingMessage } = chatUiSlice.actions;
export const chatUiReducer = chatUiSlice.reducer;

// --- notificationUiSlice.js ---
/* Same sibling-coordination need as chatUiSlice - the mobile bottom
 * navigation and the notification bell (in Navbar) are siblings, not
 * parent/child, so a plain prop can't connect them. A counter (not a
 * boolean) so requesting twice in a row still triggers a fresh open
 * even if the bell was already opened and closed in between. */
const notificationUiSlice = createSlice({
  name: 'notificationUi',
  initialState: {
    openRequestCount: 0,
  },
  reducers: {
    requestOpen(state) {
      state.openRequestCount += 1;
    },
  },
});

export const { requestOpen } = notificationUiSlice.actions;
export const notificationUiReducer = notificationUiSlice.reducer;

// --- themeSlice.js ---
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
export const themeReducer = themeSlice.reducer;
