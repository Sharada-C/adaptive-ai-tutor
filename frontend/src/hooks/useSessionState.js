import { useEffect, useState } from "react";

// useState that survives a page refresh (but not closing the tab) by
// mirroring its value into sessionStorage. Replaces the repeated
// load/save helpers and one persistence effect per field.

function load(key, fallback) {
  try {
    const value = sessionStorage.getItem(key);

    return value === null ? fallback : JSON.parse(value);
  } catch {
    return fallback;
  }
}

export function useSessionState(key, initialValue) {
  const [value, setValue] = useState(() => load(key, initialValue));

  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Storage may be full or unavailable; the app still works.
    }
  }, [key, value]);

  return [value, setValue];
}
