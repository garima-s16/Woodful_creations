import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import api from '../services/api';

const initialState = {
  projectStatuses: [],
  priorities: [],
  paymentModes: [],
  leadSources: [],
  projectTypes: [],
  expenseCategories: [],
  loading: false,
  error: null,
};

export const fetchProjectStatuses = createAsyncThunk(
  'settings/fetchProjectStatuses',
  async (_, { rejectWithValue }) => {
    try {
      const response = await api.get('/api/settings/project-statuses');
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching project statuses');
    }
  }
);

export const fetchPriorities = createAsyncThunk(
  'settings/fetchPriorities',
  async (_, { rejectWithValue }) => {
    try {
      const response = await api.get('/api/settings/priorities');
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching priorities');
    }
  }
);

export const fetchPaymentModes = createAsyncThunk(
  'settings/fetchPaymentModes',
  async (_, { rejectWithValue }) => {
    try {
      const response = await api.get('/api/settings/payment-modes');
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching payment modes');
    }
  }
);

export const fetchLeadSources = createAsyncThunk(
  'settings/fetchLeadSources',
  async (_, { rejectWithValue }) => {
    try {
      const response = await api.get('/api/settings/lead-sources');
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching lead sources');
    }
  }
);

export const fetchProjectTypes = createAsyncThunk(
  'settings/fetchProjectTypes',
  async (_, { rejectWithValue }) => {
    try {
      const response = await api.get('/api/settings/project-types');
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching project types');
    }
  }
);

export const fetchExpenseCategories = createAsyncThunk(
  'settings/fetchExpenseCategories',
  async (_, { rejectWithValue }) => {
    try {
      const response = await api.get('/api/settings/expense-categories');
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching expense categories');
    }
  }
);

const settingsSlice = createSlice({
  name: 'settings',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchProjectStatuses.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchProjectStatuses.fulfilled, (state, action) => {
        state.loading = false;
        state.projectStatuses = action.payload;
      })
      .addCase(fetchProjectStatuses.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })
      .addCase(fetchPriorities.pending, (state) => {
        state.loading = true;
      })
      .addCase(fetchPriorities.fulfilled, (state, action) => {
        state.loading = false;
        state.priorities = action.payload;
      })
      .addCase(fetchPriorities.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })
      .addCase(fetchPaymentModes.pending, (state) => {
        state.loading = true;
      })
      .addCase(fetchPaymentModes.fulfilled, (state, action) => {
        state.loading = false;
        state.paymentModes = action.payload;
      })
      .addCase(fetchPaymentModes.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })
      .addCase(fetchLeadSources.pending, (state) => {
        state.loading = true;
      })
      .addCase(fetchLeadSources.fulfilled, (state, action) => {
        state.loading = false;
        state.leadSources = action.payload;
      })
      .addCase(fetchLeadSources.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })
      .addCase(fetchProjectTypes.pending, (state) => {
        state.loading = true;
      })
      .addCase(fetchProjectTypes.fulfilled, (state, action) => {
        state.loading = false;
        state.projectTypes = action.payload;
      })
      .addCase(fetchProjectTypes.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })
      .addCase(fetchExpenseCategories.pending, (state) => {
        state.loading = true;
      })
      .addCase(fetchExpenseCategories.fulfilled, (state, action) => {
        state.loading = false;
        state.expenseCategories = action.payload;
      })
      .addCase(fetchExpenseCategories.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      });
  },
});

export const { clearError } = settingsSlice.actions;
export default settingsSlice.reducer;
