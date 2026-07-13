import { useLogout } from "../auth";
import type { User } from "../types";
import Avatar from "./Avatar";
import DropdownMenu from "./DropdownMenu";

/** Avatar button in the header that opens a profile menu (with Sign out). */
export default function UserMenu({ user }: { user: User }) {
  const logout = useLogout();

  return (
    <DropdownMenu
      label="Account menu"
      triggerClassName="avatar-btn"
      trigger={<Avatar user={user} size={34} />}
    >
      {() => (
        <>
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
        </>
      )}
    </DropdownMenu>
  );
}
