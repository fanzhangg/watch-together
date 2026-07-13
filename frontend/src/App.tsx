import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useMe } from "./auth";
import Layout from "./components/Layout";
import InvitePage from "./pages/InvitePage";
import ListPage from "./pages/ListPage";
import ListsPage from "./pages/ListsPage";
import LoginPage from "./pages/LoginPage";
import MovieDetailPage from "./pages/MovieDetailPage";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { data: user, isPending } = useMe();
  const location = useLocation();

  if (isPending) return <p className="container muted">Loading…</p>;
  // Remember where they were headed so login can send them back.
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      {/* Public: you can see what you were invited to before signing in. */}
      <Route path="/invite/:code" element={<InvitePage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route path="/" element={<ListsPage />} />
        <Route path="/lists/:id" element={<ListPage />} />
        <Route path="/lists/:id/items/:itemId" element={<MovieDetailPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
