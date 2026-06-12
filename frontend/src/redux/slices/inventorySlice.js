import { createSlice } from '@reduxjs/toolkit';

const inventorySlice = createSlice({
  name: 'inventory',
  initialState: {
    products: [],
    loading: false,
    error: null,
    filter: {
      search: '',
      category: 'all',
    },
  },
  reducers: {
    fetchStart: (state) => {
      state.loading = true;
      state.error = null;
    },
    fetchSuccess: (state, action) => {
      state.loading = false;
      state.products = action.payload;
      state.error = null;
    },
    fetchFailure: (state, action) => {
      state.loading = false;
      state.error = action.payload;
    },
    addProduct: (state, action) => {
      state.products.push(action.payload);
    },
    updateProduct: (state, action) => {
      const index = state.products.findIndex(
        (p) => p.id === action.payload.id
      );
      if (index >= 0) {
        state.products[index] = action.payload;
      }
    },
    setFilter: (state, action) => {
      state.filter = { ...state.filter, ...action.payload };
    },
  },
});

export const {
  fetchStart,
  fetchSuccess,
  fetchFailure,
  addProduct,
  updateProduct,
  setFilter,
} = inventorySlice.actions;

export default inventorySlice.reducer;