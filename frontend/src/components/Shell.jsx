import { NavLink, Outlet, useLocation, useParams } from "react-router-dom";
import { useAuth } from "../auth";

const STEPS = [
  { to: "/upload", label: "Upload material" },
  { to: "/configure", label: "Configure paper" },
];

export default function Shell() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const activePaper = location.pathname.match(/\/papers\/(\d+)\//)?.[1];
  const initials = user.name.split(" ").map((p) => p[0]).join("").slice(0, 2);

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-left">
          <span className="wordmark">Set<span>wise</span></span>
          <span className="breadcrumb">{user.department || "Setting papers"}</span>
        </div>
        <div className="topbar-right">
          <span className="role-badge">{user.role}</span>
          <span className="avatar">{initials}</span>
          <button className="link-btn" onClick={logout}>Sign out</button>
        </div>
      </header>

      <div className="workspace">
        <nav className="rail">
          <p className="rail-label">Set a paper</p>
          {STEPS.map((step, i) => (
            <NavLink key={step.to} to={step.to} className="rail-item">
              <span className="rail-num">{i + 1}</span>
              {step.label}
            </NavLink>
          ))}
          <NavLink
            to={activePaper ? `/papers/${activePaper}/edit` : "#"}
            className={`rail-item ${activePaper ? "" : "disabled"}`}
            onClick={(e) => !activePaper && e.preventDefault()}
          >
            <span className="rail-num">3</span>Edit questions
          </NavLink>
          <NavLink
            to={activePaper ? `/papers/${activePaper}/preview` : "#"}
            className={`rail-item ${activePaper ? "" : "disabled"}`}
            onClick={(e) => !activePaper && e.preventDefault()}
          >
            <span className="rail-num">4</span>Preview &amp; export
          </NavLink>

          <div className="rail-divider" />
          <NavLink to="/archive" className="rail-item">Past papers</NavLink>
        </nav>

        <main className="panel-area">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
