import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import { personalCartAPI, materialsAPI } from '../../utils/api';

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
export default cartSlice.reducer;
