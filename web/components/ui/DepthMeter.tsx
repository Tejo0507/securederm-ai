/**
 * A value from 0 to 1 as a row of extruded slats, like keys on a rack: the
 * filled ones in accent on their darker edge, the rest recessed. Slats rise
 * into place one after another when the meter first appears.
 */
export default function DepthMeter({
  value,
  label,
  segments = 20,
  className = "",
}: {
  value: number;
  /** Accessible name, e.g. "Accuracy". */
  label: string;
  segments?: number;
  className?: string;
}) {
  const clamped = Math.min(1, Math.max(0, Number.isFinite(value) ? value : 0));
  const filled = Math.round(clamped * segments);
  const percent = Math.round(clamped * 100);
  return (
    <div
      role="meter"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      aria-valuetext={`${percent}%`}
      className={`flex h-3 items-end gap-[2px] pb-[2px] ${className}`}
    >
      {Array.from({ length: segments }, (_, i) => (
        <span
          key={i}
          aria-hidden="true"
          style={{ animationDelay: `${i * 18}ms` }}
          className={`h-full flex-1 origin-bottom animate-rise rounded-[2px] ${
            i < filled
              ? "bg-accent shadow-[0_2px_0_rgb(var(--accent-edge))]"
              : "h-[70%] bg-sunken shadow-[0_2px_0_rgb(var(--line-strong))]"
          }`}
        />
      ))}
    </div>
  );
}
