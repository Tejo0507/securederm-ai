"use client";

import { forwardRef, type InputHTMLAttributes } from "react";
import { Input } from "@/components/ui/Field";
import { IconEye, IconEyeOff } from "@/components/ui/icons";

/** Password field with a show/hide toggle inside it. Visibility is controlled by the caller. */
const PasswordInput = forwardRef<
  HTMLInputElement,
  Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
    visible: boolean;
    onToggle: () => void;
    toggleLabel?: [show: string, hide: string];
  }
>(function PasswordInput({ visible, onToggle, toggleLabel = ["Show password", "Hide password"], className = "", ...rest }, ref) {
  return (
    <div className="relative">
      <Input ref={ref} type={visible ? "text" : "password"} className={`pr-11 ${className}`} {...rest} />
      <button
        type="button"
        onClick={onToggle}
        aria-label={visible ? toggleLabel[1] : toggleLabel[0]}
        aria-pressed={visible}
        className="absolute right-1 top-1/2 flex h-8 w-8 -translate-y-1/2 items-center justify-center rounded text-ink-3 transition-colors hover:bg-ink/[0.06] hover:text-ink"
      >
        {visible ? <IconEyeOff size={16} /> : <IconEye size={16} />}
      </button>
    </div>
  );
});

export default PasswordInput;
