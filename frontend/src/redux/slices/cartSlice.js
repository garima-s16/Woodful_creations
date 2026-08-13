import { createSlice } from '@reduxjs/toolkit';

/**
 * Purchase Cart — lets a user build up a "to purchase" list while
 * browsing the Material Catalog, the same way an e-commerce cart works.
 * This is a client-side draft only (nothing is created on the backend
 * until the user acts on it from Purchases), so it's persisted to
 * localStorage rather than the API — closing the tab shouldn't lose it.
 */
const STORAGE_KEY = 'woodful_purchase_cart_v1';

function loadInitialItems() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function persist(items) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } catch {
    // Storage can fail (private browsing, quota) - cart still works in-memory.
  }
}

const cartSlice = createSlice({
  name: 'cart',
  initialState: {
    items: loadInitialItems(),
  },
  reducers: {
    addToCart(state, action) {
      const { materialId, name, unit, rate, supplierId, supplierName, quantity } = action.payload;
      const qty = Number(quantity) > 0 ? Number(quantity) : 1;
      const existing = state.items.find((i) => i.materialId === materialId);
      if (existing) {
        existing.quantity += qty;
      } else {
        state.items.push({ materialId, name, unit, rate: rate || 0, supplierId, supplierName, quantity: qty });
      }
      persist(state.items);
    },
    updateQuantity(state, action) {
      const { materialId, quantity } = action.payload;
      const item = state.items.find((i) => i.materialId === materialId);
      if (item) {
        item.quantity = Math.max(0, Number(quantity) || 0);
        if (item.quantity === 0) {
          state.items = state.items.filter((i) => i.materialId !== materialId);
        }
      }
      persist(state.items);
    },
    removeFromCart(state, action) {
      state.items = state.items.filter((i) => i.materialId !== action.payload);
      persist(state.items);
    },
    clearCart(state) {
      state.items = [];
      persist(state.items);
    },
  },
});

export const { addToCart, updateQuantity, removeFromCart, clearCart } = cartSlice.actions;
export default cartSlice.reducer;
