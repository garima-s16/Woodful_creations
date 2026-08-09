import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import api from '../services/api';

const initialState = {
  orders: [],
  currentOrder: null,
  orderProfitability: null,
  activeOrders: [],
  loading: false,
  error: null,
};

export const fetchOrders = createAsyncThunk(
  'orders/fetchOrders',
  async ({ skip = 0, limit = 50, status = null, client_id = null }, { rejectWithValue }) => {
    try {
      const response = await api.get('/api/orders/', {
        params: { skip, limit, status, client_id },
      });
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching orders');
    }
  }
);

export const fetchActiveOrders = createAsyncThunk(
  'orders/fetchActiveOrders',
  async (_, { rejectWithValue }) => {
    try {
      const response = await api.get('/api/orders/active/list');
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching active orders');
    }
  }
);

export const fetchOrderProfitability = createAsyncThunk(
  'orders/fetchOrderProfitability',
  async (orderId, { rejectWithValue }) => {
    try {
      const response = await api.get(`/api/orders/${orderId}/profitability`);
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching order profitability');
    }
  }
);

export const createOrder = createAsyncThunk(
  'orders/createOrder',
  async (orderData, { rejectWithValue }) => {
    try {
      const response = await api.post('/api/orders/', orderData);
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error creating order');
    }
  }
);

export const updateOrder = createAsyncThunk(
  'orders/updateOrder',
  async ({ id, data }, { rejectWithValue }) => {
    try {
      const response = await api.put(`/api/orders/${id}`, data);
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error updating order');
    }
  }
);

export const updateOrderStatus = createAsyncThunk(
  'orders/updateOrderStatus',
  async ({ id, status }, { rejectWithValue }) => {
    try {
      const response = await api.put(`/api/orders/${id}/status`, { status });
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error updating order status');
    }
  }
);

const ordersSlice = createSlice({
  name: 'orders',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchOrders.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchOrders.fulfilled, (state, action) => {
        state.loading = false;
        state.orders = action.payload;
      })
      .addCase(fetchOrders.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })
      .addCase(fetchActiveOrders.fulfilled, (state, action) => {
        state.activeOrders = action.payload;
      })
      .addCase(fetchOrderProfitability.fulfilled, (state, action) => {
        state.orderProfitability = action.payload;
      })
      .addCase(createOrder.pending, (state) => {
        state.loading = true;
      })
      .addCase(createOrder.fulfilled, (state, action) => {
        state.loading = false;
        state.orders.push(action.payload);
      })
      .addCase(createOrder.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })
      .addCase(updateOrder.fulfilled, (state, action) => {
        const index = state.orders.findIndex(o => o.id === action.payload.id);
        if (index !== -1) {
          state.orders[index] = action.payload;
        }
      })
      .addCase(updateOrderStatus.fulfilled, (state, action) => {
        const index = state.orders.findIndex(o => o.id === action.payload.id);
        if (index !== -1) {
          state.orders[index] = action.payload;
        }
      });
  },
});

export const { clearError } = ordersSlice.actions;
export default ordersSlice.reducer;
