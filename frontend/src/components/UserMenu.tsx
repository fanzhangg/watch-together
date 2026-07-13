import { useEffect, useRef, useState } from "react";
import { useLogout } from "../auth";
import type { User } from "../types";

function initials(user: User): string {
  const name = user.display_name?.trim();
  if (name) {
    return name
      .split(/\s+/)
      .slice(0, 2)
      .map((w) => w[0])
      .join("")
      .toUpperCase();
  }
  return (user.email[0] ?? "?").toUpperCase();
}

function Avatar({ user, size }: { user: User; size: number }) {
  const style = { width: size, height: size, fontSize: size * 0.4 };
  if (user.avatar_url) {
    return (
      <img
        className="avatar"
        src={user.avatar_url}
        alt=""
        style={style}
        // Google's avatar CDN 403s when a referrer is sent.
        referrerPolicy="no-referrer"
      />
    );
  }
  return (
    <span className="avatar avatar-initials" style={style} aria-hidden="true">
      {initials(user)}
    </span>
  );
}

/** Avatar button in the header that opens a profile menu (with Sign out). */
export default function UserMenu({ user }: { user: User }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const logout = useLogout();

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
    <div className="user-menu" ref={ref}>
      <button
        className="avatar-btn"
        aria-label="Account menu"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <Avatar user={user} size={34} />
      </button>

      {open && (
        <div className="menu-popover" role="menu">
          <div className="menu-header">
            <Avatar user={user} size={40} />
            <div className="menu-identity">
              {user.display_name && (
                <div className="menu-name">{user.display_name}</div>
              )}
              <div className="menu-email">{user.email}</div>
            </div>
          </div>

          <div className="menu-sep" />

          <button
            className="menu-item"
            role="menuitem"
            onClick={() => logout.mutate()}
            disabled={logout.isPending}
          >
            {logout.isPending ? "Signing out…" : "Sign out"}
          </button>
        </div>
      )}
    </div>
  );
}
