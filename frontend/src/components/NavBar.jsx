import React from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext.jsx";

export default function NavBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <header className="navbar">
      <Link to="/" className="navbar-brand">
        🌐 Translation System
      </Link>
      {user && (
        <nav className="navbar-links">
          <Link to="/">Translate</Link>
          <Link to="/history">History</Link>
          <Link to="/glossary">Glossary</Link>
          {user.is_admin && <Link to="/admin">Admin</Link>}
          <span className="navbar-user">{user.email}</span>
          <button
            className="btn-link"
            onClick={() => {
              logout();
              navigate("/login");
            }}
          >
            Log out
          </button>
        </nav>
      )}
    </header>
  );
}
