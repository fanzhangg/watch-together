import type { User } from "../types";

export function initials(user: User): string {
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

export function displayName(user: User): string {
  return user.display_name?.trim() || user.email;
}

/**
 * A user's picture, falling back to their initials. Shared by the header menu
 * and the list's member row.
 *
 * `label` makes the avatar meaningful on its own — in the member row it's the
 * only thing identifying the person, so it needs a name for hover and for a
 * screen reader.
 */
export default function Avatar({
  user,
  size,
  label,
}: {
  user: User;
  size: number;
  label?: string;
}) {
  const style = { width: size, height: size, fontSize: size * 0.4 };
  const named = label
    ? { title: label, role: "img" as const, "aria-label": label }
    : { "aria-hidden": true };

  if (user.avatar_url) {
    return (
      <img
        className="avatar"
        src={user.avatar_url}
        // Decorative next to a name (the header menu); the only identifier when
        // it stands alone (the member row).
        alt={label ?? ""}
        title={label}
        style={style}
        // Google's avatar CDN 403s when a referrer is sent.
        referrerPolicy="no-referrer"
      />
    );
  }
  return (
    <span className="avatar avatar-initials" style={style} {...named}>
      {initials(user)}
    </span>
  );
}
