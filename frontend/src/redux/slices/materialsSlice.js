import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import api from '../services/api';

const initialState = {
  materials: [],
  currentMaterial: null,
  lowStockMaterials: [],
  stockSummary: null,
  stockByCategory: {},
  loading: false,
  error: null,
};

export const fetchMaterials = createAsyncThunk(
  'materials/fetchMaterials',
  async ({ skip = 0, limit = 50, category = null }, { rejectWithValue }) => {
    try {
      const response = await api.get('/api/materials/', {
        params: { skip, limit, category },
      });
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching materials');
    }
  }
);

export const fetchLowStockMaterials = createAsyncThunk(
  'materials/fetchLowStockMaterials',
  async (_, { rejectWithValue }) => {
    try {
      const response = await api.get('/api/materials/stock-status/low-stock');
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching low stock materials');
    }
  }
);

export const fetchStockSummary = createAsyncThunk(
  'materials/fetchStockSummary',
  async (_, { rejectWithValue }) => {
    try {
      const response = await api.get('/api/materials/stock-status/summary');
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching stock summary');
    }
  }
);

export const fetchStockByCategory = createAsyncThunk(
  'materials/fetchStockByCategory',
  async (_, { rejectWithValue }) => {
    try {
      const response = await api.get('/api/materials/stock-status/by-category');
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching stock by category');
    }
  }
);

export const createMaterial = createAsyncThunk(
  'materials/createMaterial',
  async (materialData, { rejectWithValue }) => {
    try {
      const response = await api.post('/api/materials/', materialData);
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error creating material');
    }
  }
);

export const updateMaterial = createAsyncThunk(
  'materials/updateMaterial',
  async ({ id, data }, { rejectWithValue }) => {
    try {
      const response = await api.put(`/api/materials/${id}`, data);
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error updating material');
    }
  }
);

const materialsSlice = createSlice({
  name: 'materials',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchMaterials.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchMaterials.fulfilled, (state, action) => {
        state.loading = false;
        state.materials = action.payload;
      })
      .addCase(fetchMaterials.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })
      .addCase(fetchLowStockMaterials.fulfilled, (state, action) => {
        state.lowStockMaterials = action.payload.materials || [];
      })
      .addCase(fetchStockSummary.fulfilled, (state, action) => {
        state.stockSummary = action.payload;
      })
      .addCase(fetchStockByCategory.fulfilled, (state, action) => {
        state.stockByCategory = action.payload;
      })
      .addCase(createMaterial.pending, (state) => {
        state.loading = true;
      })
      .addCase(createMaterial.fulfilled, (state, action) => {
        state.loading = false;
        state.materials.push(action.payload);
      })
      .addCase(createMaterial.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })
      .addCase(updateMaterial.pending, (state) => {
        state.loading = true;
      })
      .addCase(updateMaterial.fulfilled, (state, action) => {
        state.loading = false;
        const index = state.materials.findIndex(m => m.id === action.payload.id);
        if (index !== -1) {
          state.materials[index] = action.payload;
        }
      })
      .addCase(updateMaterial.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      });
  },
});

export const { clearError } = materialsSlice.actions;
export default materialsSlice.reducer;
