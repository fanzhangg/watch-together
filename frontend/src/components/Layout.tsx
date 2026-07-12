import { Link, Outlet } from "react-router-dom";
import { useLogout, useMe } from "../auth";

export default function Layout() {
  const { data: user } = useMe();
  const logout = useLogout();

  return (
    <>
      <header className="app-header">
        <Link to="/" className="brand">
          🎬 Watch Together
        </Link>
        {user && (
          <div className="header-user">
            <span>{user.display_name ?? user.email}</span>
            <button
              className="ghost small"
              onClick={() => logout.mutate()}
              disabled={logout.isPending}
            >
              Sign out
            </button>
          </div>
        )}
      </header>
      <main className="container">
        <Outlet />
      </main>
    </>
  );
}
