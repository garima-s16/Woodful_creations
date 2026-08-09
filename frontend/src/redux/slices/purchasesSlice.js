import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import api from '../services/api';

const initialState = {
  purchases: [],
  currentPurchase: null,
  unpaidPurchases: [],
  loading: false,
  error: null,
};

export const fetchPurchases = createAsyncThunk(
  'purchases/fetchPurchases',
  async ({ skip = 0, limit = 50, supplier_id = null, payment_status = null }, { rejectWithValue }) => {
    try {
      const response = await api.get('/api/purchases/', {
        params: { skip, limit, supplier_id, payment_status },
      });
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching purchases');
    }
  }
);

export const fetchUnpaidPurchases = createAsyncThunk(
  'purchases/fetchUnpaidPurchases',
  async (_, { rejectWithValue }) => {
    try {
      const response = await api.get('/api/purchases/payment-status/unpaid');
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching unpaid purchases');
    }
  }
);

export const createPurchase = createAsyncThunk(
  'purchases/createPurchase',
  async (purchaseData, { rejectWithValue }) => {
    try {
      const response = await api.post('/api/purchases/', purchaseData);
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error creating purchase');
    }
  }
);

export const updatePurchaseStatus = createAsyncThunk(
  'purchases/updatePurchaseStatus',
  async ({ id, payment_status }, { rejectWithValue }) => {
    try {
      const response = await api.put(`/api/purchases/${id}/payment-status`, { payment_status });
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error updating purchase status');
    }
  }
);

const purchasesSlice = createSlice({
  name: 'purchases',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchPurchases.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchPurchases.fulfilled, (state, action) => {
        state.loading = false;
        state.purchases = action.payload;
      })
      .addCase(fetchPurchases.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })
      .addCase(fetchUnpaidPurchases.fulfilled, (state, action) => {
        state.unpaidPurchases = action.payload;
      })
      .addCase(createPurchase.pending, (state) => {
        state.loading = true;
      })
      .addCase(createPurchase.fulfilled, (state, action) => {
        state.loading = false;
        state.purchases.push(action.payload);
      })
      .addCase(createPurchase.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })
      .addCase(updatePurchaseStatus.fulfilled, (state, action) => {
        const index = state.purchases.findIndex(p => p.id === action.payload.id);
        if (index !== -1) {
          state.purchases[index] = action.payload;
        }
      });
  },
});

export const { clearError } = purchasesSlice.actions;
export default purchasesSlice.reducer;
