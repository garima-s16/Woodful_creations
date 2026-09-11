import { configureStore } from '@reduxjs/toolkit';
import { authReducer, cartReducer, chatUiReducer, notificationUiReducer, themeReducer } from './slices';

const store = configureStore({
  reducer: {
    auth: authReducer,
    cart: cartReducer,
    chatUi: chatUiReducer,
    notificationUi: notificationUiReducer,
    theme: themeReducer,
  },
});

export default store;
