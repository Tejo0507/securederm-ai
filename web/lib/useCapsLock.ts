"use client";

import { KeyboardEvent, useState } from "react";

/**
 * Whether Caps Lock is on while typing in a password field, so the form can say
 * so: a password that "doesn't work" is very often just Caps Lock. Spread
 * `handlers` onto the input. The state clears when the field loses focus.
 */
export function useCapsLock() {
  const [capsLock, setCapsLock] = useState(false);
  const update = (e: KeyboardEvent<HTMLInputElement>) =>
    setCapsLock(e.getModifierState?.("CapsLock") ?? false);
  return {
    capsLock,
    handlers: { onKeyDown: update, onKeyUp: update, onBlur: () => setCapsLock(false) },
  };
}
