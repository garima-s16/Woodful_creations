/* Classifies a failed primary-record fetch into an honest message the
 * user can act on. Shared by every detail page's primary load instead
 * of duplicating this logic per page (Client/Employee/Material/Supplier
 * DetailPage already did this inline; this is the same behavior,
 * extracted so the 7 pages fixed alongside it don't reimplement it).
 *
 * The core rule: only a genuine 404 means "this record does not
 * exist" - every other failure (403 permission, 5xx server error,
 * a network failure, or anything unexpected) must never be presented
 * as "not found", since that implies something false about whether
 * the record exists. A 401 is not handled specially here - the
 * global response interceptor in api.js already redirects to /login
 * on 401 before this would meaningfully render, so labeling it
 * "not found" is the only thing that must be avoided for it, not a
 * distinct message of its own.
 */
export function classifyLoadError(err, label) {
  const status = err?.response?.status;

  if (status === 404) {
    return { message: `This ${label} could not be found.`, isNotFound: true };
  }
  if (status === 403) {
    return { message: `You do not have permission to view this ${label}.`, isNotFound: false };
  }
  if (status >= 500) {
    return { message: `Something went wrong loading this ${label}. Please try again.`, isNotFound: false };
  }
  if (!err?.response) {
    // No response at all (network failure, timeout, connection refused)
    // as distinct from a response that arrived with an error status.
    return { message: 'Unable to connect. Check your network and try again.', isNotFound: false };
  }
  return { message: `Unable to load this ${label}. Please try again.`, isNotFound: false };
}
