import { useEffect, useState } from "react";

// useState that survives page navigation (like Streamlit's session_state).
export function useSessionState(key, initial) {
  const [value, setValue] = useState(() => {
    try {
      const raw = sessionStorage.getItem(key);
      return raw ? JSON.parse(raw) : initial;
    } catch {
      return initial;
    }
  });
  useEffect(() => {
    try { sessionStorage.setItem(key, JSON.stringify(value)); } catch { /* quota: ignore */ }
  }, [key, value]);
  return [value, setValue];
}
