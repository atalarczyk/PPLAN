import { Link } from "react-router-dom";

import { routePaths } from "../routePaths";

import { useAuth } from "./AuthProvider";

export function UnauthorizedPage() {
  return (
    <section>
      <h2>Authentication required</h2>
      <p>You must sign in with your Microsoft 365 identity before accessing the platform.</p>
      <p>
        Continue to <Link to={routePaths.signIn}>sign in</Link>.
      </p>
    </section>
  );
}

export function ForbiddenPage() {
  const { state } = useAuth();

  return (
    <section>
      <h2>Access denied</h2>
      <p>{state.errorMessage ?? "You do not have required role or scope permissions for this route."}</p>
      <p>
        Return to <Link to={routePaths.projects}>projects</Link>.
      </p>
    </section>
  );
}

export function SignInPage() {
  return (
    <section>
      <h2>Sign in</h2>
      <p>
        Microsoft 365 interactive sign-in integration is planned in next milestone. For current phase,
        backend trusted-header/dev-principal mode drives session bootstrap.
      </p>
      <p>
        Continue to <Link to={routePaths.authCallback}>auth callback</Link>.
      </p>
    </section>
  );
}

export function AuthCallbackPage() {
  const { refresh, state } = useAuth();

  return (
    <section>
      <h2>Auth callback</h2>
      <p>
        Callback endpoint placeholder for future Microsoft identity flow. Use refresh to reload access
        context from backend.
      </p>
      <button type="button" onClick={() => void refresh()}>
        Refresh session context
      </button>
      <p>Current state: {state.status}</p>
      <p>
        Open <Link to={routePaths.projects}>application shell</Link>.
      </p>
    </section>
  );
}

