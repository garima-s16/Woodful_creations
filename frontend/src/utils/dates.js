/** Today's date as YYYY-MM-DD, for pre-filling <input type="date"> fields
 * so users aren't manually picking "today" on every quick-action form. */
export function today() {
  return new Date().toISOString().slice(0, 10);
}
