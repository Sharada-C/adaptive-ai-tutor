// Remembers the signed-in user between page loads. localStorage can be
// blocked or unavailable (private windows, strict settings), so every
// access is guarded and the app still works for the current visit.
//
// Note: a token in localStorage can be read by any script running on
// the page. That is acceptable for this app (no third-party scripts),
// but keep it in mind before adding any.

const KEY = "tutor_auth";

export function loadAuth() {
  try {
    const raw = localStorage.getItem(KEY);

    if (!raw) {
      return null;
    }

    const auth = JSON.parse(raw);

    return auth?.token && auth?.user ? auth : null;
  } catch {
    return null;
  }
}

export function saveAuth(auth) {
  try {
    localStorage.setItem(KEY, JSON.stringify(auth));
  } catch {
    // The session still works until the page is closed.
  }
}

export function clearAuth() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // Nothing to clear.
  }
}
