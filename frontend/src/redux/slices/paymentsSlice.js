import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import api from '../services/api';

const initialState = {
  payments: [],
  currentPayment: null,
  orderPaymentSummary: null,
  clientPaymentSummary: null,
  overduePayments: [],
  loading: false,
  error: null,
};

export const fetchPayments = createAsyncThunk(
  'payments/fetchPayments',
  async ({ skip = 0, limit = 50, order_id = null, client_id = null, payment_mode = null }, { rejectWithValue }) => {
    try {
      const response = await api.get('/api/payments/', {
        params: { skip, limit, order_id, client_id, payment_mode },
      });
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching payments');
    }
  }
);

export const fetchOrderPaymentSummary = createAsyncThunk(
  'payments/fetchOrderPaymentSummary',
  async (orderId, { rejectWithValue }) => {
    try {
      const response = await api.get(`/api/payments/order/${orderId}/summary`);
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching payment summary');
    }
  }
);

export const fetchClientPaymentSummary = createAsyncThunk(
  'payments/fetchClientPaymentSummary',
  async ({ clientId, days = 30 }, { rejectWithValue }) => {
    try {
      const response = await api.get(`/api/payments/client/${clientId}/summary`, {
        params: { days },
      });
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching client payment summary');
    }
  }
);

export const fetchOverduePayments = createAsyncThunk(
  'payments/fetchOverduePayments',
  async (days = 30, { rejectWithValue }) => {
    try {
      const response = await api.get('/api/payments/overdue/list', {
        params: { days },
      });
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching overdue payments');
    }
  }
);

export const createPayment = createAsyncThunk(
  'payments/createPayment',
  async (paymentData, { rejectWithValue }) => {
    try {
      const response = await api.post('/api/payments/', paymentData);
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error creating payment');
    }
  }
);

const paymentsSlice = createSlice({
  name: 'payments',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchPayments.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchPayments.fulfilled, (state, action) => {
        state.loading = false;
        state.payments = action.payload;
      })
      .addCase(fetchPayments.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })
      .addCase(fetchOrderPaymentSummary.fulfilled, (state, action) => {
        state.orderPaymentSummary = action.payload;
      })
      .addCase(fetchClientPaymentSummary.fulfilled, (state, action) => {
        state.clientPaymentSummary = action.payload;
      })
      .addCase(fetchOverduePayments.fulfilled, (state, action) => {
        state.overduePayments = action.payload;
      })
      .addCase(createPayment.pending, (state) => {
        state.loading = true;
      })
      .addCase(createPayment.fulfilled, (state, action) => {
        state.loading = false;
        state.payments.push(action.payload);
      })
      .addCase(createPayment.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      });
  },
});

export const { clearError } = paymentsSlice.actions;
export default paymentsSlice.reducer;
