import { useEffect, type ReactNode } from "react";

/**
 * Shared modal shell: backdrop click, Escape to close, and a body scroll lock so
 * the page doesn't scroll behind it (very noticeable on mobile).
 *
 * - "sheet"   — tall, scrollable; becomes a full-screen sheet on mobile (search)
 * - "compact" — a small centred card (invite link)
 */
export default function Modal({
  variant = "compact",
  label,
  onClose,
  children,
}: {
  variant?: "sheet" | "compact";
  label: string;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    document.body.classList.add("no-scroll");
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.classList.remove("no-scroll");
    };
  }, [onClose]);

  return (
    <div className={`dialog-backdrop ${variant}`} onClick={onClose}>
      <div
        className={`dialog ${variant}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={label}
      >
        {children}
      </div>
    </div>
  );
}
