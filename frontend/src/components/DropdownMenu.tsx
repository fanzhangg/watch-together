import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * A button that opens a popover menu. Closes on Escape, on an outside
 * click/tap, and after a menu item runs (items get a `close` callback).
 *
 * Shared by the header avatar menu and the per-list "⋯" menu.
 */
export default function DropdownMenu({
  label,
  trigger,
  triggerClassName,
  children,
}: {
  label: string;
  trigger: ReactNode;
  triggerClassName?: string;
  children: (close: () => void) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointerDown = (e: MouseEvent | TouchEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("touchstart", onPointerDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("touchstart", onPointerDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="menu-anchor" ref={ref}>
      <button
        className={triggerClassName}
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        {trigger}
      </button>

      {open && (
        <div className="menu-popover" role="menu">
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}
