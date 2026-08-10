import { configureStore } from '@reduxjs/toolkit';
import authReducer from './slices/authSlice';
import inventoryReducer from './slices/inventorySlice';

const store = configureStore({
  reducer: {
    auth: authReducer,
    inventory: inventoryReducer,
  },
});

export default store;
