import { createSlice } from '@reduxjs/toolkit';

/* Coordinates the top command bar (Navbar) with the actual chat panel
 * (ChatWidget) - they're siblings, not parent/child, so a plain prop
 * can't connect them. When the command bar is submitted, it dispatches
 * openWithMessage(text); ChatWidget watches pendingMessage, opens
 * itself, sends that text through its own real send() flow (so it
 * goes through the exact same backend/propose-confirm logic as typing
 * directly into the panel - no separate code path), then clears it. */
const chatUiSlice = createSlice({
  name: 'chatUi',
  initialState: {
    pendingMessage: null,
  },
  reducers: {
    openWithMessage(state, action) {
      state.pendingMessage = action.payload;
    },
    clearPendingMessage(state) {
      state.pendingMessage = null;
    },
  },
});

export const { openWithMessage, clearPendingMessage } = chatUiSlice.actions;
export default chatUiSlice.reducer;
