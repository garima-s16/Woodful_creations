import { configureStore } from '@reduxjs/toolkit';
import settingsReducer from './slices/settingsSlice';
import suppliersReducer from './slices/suppliersSlice';
import materialsReducer from './slices/materialsSlice';
import purchasesReducer from './slices/purchasesSlice';
import issuesReducer from './slices/issuesSlice';
import ordersReducer from './slices/ordersSlice';
import paymentsReducer from './slices/paymentsSlice';

const store = configureStore({
  reducer: {
    settings: settingsReducer,
    suppliers: suppliersReducer,
    materials: materialsReducer,
    purchases: purchasesReducer,
    issues: issuesReducer,
    orders: ordersReducer,
    payments: paymentsReducer,
  },
});

export default store;
