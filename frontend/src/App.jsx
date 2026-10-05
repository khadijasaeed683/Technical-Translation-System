import React from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import NavBar from "./components/NavBar.jsx";
import { useAuth } from "./context/AuthContext.jsx";
import Admin from "./pages/Admin.jsx";
import Glossary from "./pages/Glossary.jsx";
import History from "./pages/History.jsx";
import Login from "./pages/Login.jsx";
import Signup from "./pages/Signup.jsx";
import Translate from "./pages/Translate.jsx";

function Protected({ children, adminOnly = false }) {
  const { user, ready } = useAuth();
  if (!ready) return null;
  if (!user) return <Navigate to="/login" replace />;
  if (adminOnly && !user.is_admin) return <Navigate to="/" replace />;
  return children;
}

export default function App() {
  const { user } = useAuth();

  return (
    <div className="app-shell">
      <NavBar />
      <main className="app-main">
        <Routes>
          <Route path="/login" element={user ? <Navigate to="/" replace /> : <Login />} />
          <Route path="/signup" element={user ? <Navigate to="/" replace /> : <Signup />} />
          <Route
            path="/"
            element={
              <Protected>
                <Translate />
              </Protected>
            }
          />
          <Route
            path="/history"
            element={
              <Protected>
                <History />
              </Protected>
            }
          />
          <Route
            path="/glossary"
            element={
              <Protected>
                <Glossary />
              </Protected>
            }
          />
          <Route
            path="/admin"
            element={
              <Protected adminOnly>
                <Admin />
              </Protected>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
