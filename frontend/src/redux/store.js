import { configureStore } from '@reduxjs/toolkit';
import authReducer from './slices/authSlice';
import cartReducer from './slices/cartSlice';
import chatUiReducer from './slices/chatUiSlice';

const store = configureStore({
  reducer: {
    auth: authReducer,
    cart: cartReducer,
    chatUi: chatUiReducer,
  },
});

export default store;
