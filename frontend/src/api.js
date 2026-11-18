// Small fetch helpers shared by every page. The login token is an httpOnly cookie (P7-35): the
// browser sends it, this code never sees it.

export class ApiError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

function messageFor(status, detail) {
  if (typeof detail === "string" && detail) return detail;
  if (status === 403) return "This page is only for Admin accounts.";
  if (status >= 500) return `The server could not finish the request (error ${status}). Try again in a moment.`;
  return `The server answered with an error (${status}).`;
}

// Returns the parsed JSON. Throws ApiError (status 0 = the server could not be reached).
// onSessionExpired is called on 401, then the error is thrown so the caller stops.
export async function api(path, { method = "GET", json, form, signal, onSessionExpired } = {}) {
  const init = { method, signal, headers: {} };
  if (json !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(json);
  } else if (form) {
    init.body = form;
  }
  let response;
  try {
    response = await fetch(path, init);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ApiError(0, "Could not reach the server. Check your connection and try again.");
  }
  if (response.status === 401) {
    onSessionExpired?.();
    throw new ApiError(401, "Your session has ended. Please log in again.");
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(response.status, messageFor(response.status, body?.detail));
  return body;
}
