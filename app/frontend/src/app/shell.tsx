import { Link, Outlet } from "react-router-dom";

import { useAuth } from "./auth/AuthProvider";
import { buildPrimaryNavigation } from "./navigation";

export function AppShell() {
  const { state } = useAuth();
  const navItems = buildPrimaryNavigation(state.session);

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>PPLAN</h1>
        <nav>
          {navItems.map((item) => {
            if (item.enabled) {
              return (
                <Link key={item.key} to={item.to}>
                  {item.label}
                </Link>
              );
            }

            return (
              <span key={item.key} className="app-nav-disabled" title={item.reason}>
                {item.label}
              </span>
            );
          })}
        </nav>
        {state.session ? <div className="app-user">{state.session.user.displayName}</div> : null}
      </header>
      <main className="app-content">
        <Outlet />
      </main>
    </div>
  );
}

