import { createSlice, createAsyncThunk } from '@reduxjs/toolkit';
import api from '../services/api';

const initialState = {
  issues: [],
  currentIssue: null,
  projectIssues: [],
  loading: false,
  error: null,
};

export const fetchIssues = createAsyncThunk(
  'issues/fetchIssues',
  async ({ skip = 0, limit = 50, project_id = null, department = null }, { rejectWithValue }) => {
    try {
      const response = await api.get('/api/issues/', {
        params: { skip, limit, project_id, department },
      });
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching issues');
    }
  }
);

export const fetchProjectIssues = createAsyncThunk(
  'issues/fetchProjectIssues',
  async (projectId, { rejectWithValue }) => {
    try {
      const response = await api.get(`/api/issues/project/${projectId}/issues`);
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error fetching project issues');
    }
  }
);

export const createIssue = createAsyncThunk(
  'issues/createIssue',
  async (issueData, { rejectWithValue }) => {
    try {
      const response = await api.post('/api/issues/', issueData);
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error creating issue');
    }
  }
);

export const updateIssue = createAsyncThunk(
  'issues/updateIssue',
  async ({ id, data }, { rejectWithValue }) => {
    try {
      const response = await api.put(`/api/issues/${id}`, data);
      return response.data;
    } catch (error) {
      return rejectWithValue(error.response?.data || 'Error updating issue');
    }
  }
);

const issuesSlice = createSlice({
  name: 'issues',
  initialState,
  reducers: {
    clearError: (state) => {
      state.error = null;
    },
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchIssues.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchIssues.fulfilled, (state, action) => {
        state.loading = false;
        state.issues = action.payload;
      })
      .addCase(fetchIssues.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })
      .addCase(fetchProjectIssues.fulfilled, (state, action) => {
        state.projectIssues = action.payload;
      })
      .addCase(createIssue.pending, (state) => {
        state.loading = true;
      })
      .addCase(createIssue.fulfilled, (state, action) => {
        state.loading = false;
        state.issues.push(action.payload);
      })
      .addCase(createIssue.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload;
      })
      .addCase(updateIssue.fulfilled, (state, action) => {
        const index = state.issues.findIndex(i => i.id === action.payload.id);
        if (index !== -1) {
          state.issues[index] = action.payload;
        }
      });
  },
});

export const { clearError } = issuesSlice.actions;
export default issuesSlice.reducer;
