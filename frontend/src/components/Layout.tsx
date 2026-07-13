import { Link, Outlet } from "react-router-dom";
import { useMe } from "../auth";
import UserMenu from "./UserMenu";

export default function Layout() {
  const { data: user } = useMe();

  return (
    <>
      <header className="app-header">
        <Link to="/" className="brand">
          🎬 Watch Together
        </Link>
        {user && <UserMenu user={user} />}
      </header>
      <main className="container">
        <Outlet />
      </main>
    </>
  );
}
