// Remembers which profile this browser last used, so a page refresh does
// not ask for the name again. localStorage can be blocked or unavailable
// (private windows, strict settings), so every access is guarded.

const KEY = "tutor_profile_name";

export function loadUsername() {
  try {
    return localStorage.getItem(KEY) || "";
  } catch {
    return "";
  }
}

export function saveUsername(name) {
  try {
    localStorage.setItem(KEY, name);
  } catch {
    // The profile still works for this visit.
  }
}

export function forgetUsername() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // Nothing to clear.
  }
}
