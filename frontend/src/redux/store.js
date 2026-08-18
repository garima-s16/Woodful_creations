import { configureStore } from '@reduxjs/toolkit';
import authReducer from './slices/authSlice';
import cartReducer from './slices/cartSlice';
import chatUiReducer from './slices/chatUiSlice';
import notificationUiReducer from './slices/notificationUiSlice';

const store = configureStore({
  reducer: {
    auth: authReducer,
    cart: cartReducer,
    chatUi: chatUiReducer,
    notificationUi: notificationUiReducer,
  },
});

export default store;
