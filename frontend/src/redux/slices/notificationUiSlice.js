import { createSlice } from '@reduxjs/toolkit';

/* Same sibling-coordination need as chatUiSlice - the mobile bottom
 * navigation and the notification bell (in Navbar) are siblings, not
 * parent/child, so a plain prop can't connect them. A counter (not a
 * boolean) so requesting twice in a row still triggers a fresh open
 * even if the bell was already opened and closed in between. */
const notificationUiSlice = createSlice({
  name: 'notificationUi',
  initialState: {
    openRequestCount: 0,
  },
  reducers: {
    requestOpen(state) {
      state.openRequestCount += 1;
    },
  },
});

export const { requestOpen } = notificationUiSlice.actions;
export default notificationUiSlice.reducer;
