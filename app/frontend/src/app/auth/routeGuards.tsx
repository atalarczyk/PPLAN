import type { ReactNode } from "react";
import { Navigate, useParams } from "react-router-dom";

import { routePaths } from "../routePaths";

import {
  canAccessRoute as canAccessRouteForSession,
  inferBusinessUnitIdFromRouteParams,
  type PermissionKey,
} from "./permissions";
import type { AppRole, AuthState } from "./types";
import { useAuth } from "./AuthProvider";

interface GuardRequirements {
  roles?: AppRole[];
  permission?: PermissionKey;
  requireScope?: "businessUnit" | "project";
}

interface ProtectedRouteProps {
  children: ReactNode;
  requirements?: GuardRequirements;
}

export type RouteGuardDecision =
  | "loading"
  | "redirect-unauthorized"
  | "redirect-forbidden"
  | "error"
  | "allow";

function buildScopeRequirement(
  requireScope: GuardRequirements["requireScope"],
  params: Readonly<Record<string, string | undefined>>,
): { scope?: { businessUnitId?: string; projectId?: string }; hasRequiredContext: boolean } {
  if (!requireScope) {
    return { hasRequiredContext: true };
  }

  if (requireScope === "businessUnit") {
    const businessUnitId = params.businessUnitId;
    if (!businessUnitId) {
      return { hasRequiredContext: false };
    }
    return {
      hasRequiredContext: true,
      scope: { businessUnitId },
    };
  }

  if (requireScope === "project") {
    const projectId = params.projectId;
    if (!projectId) {
      return { hasRequiredContext: false };
    }
    const inferredBusinessUnitId = inferBusinessUnitIdFromRouteParams(params);
    return {
      hasRequiredContext: true,
      scope: {
        projectId,
        businessUnitId: inferredBusinessUnitId,
      },
    };
  }

  return { hasRequiredContext: true };
}

export function evaluateProtectedRouteDecision(args: {
  state: AuthState;
  params: Readonly<Record<string, string | undefined>>;
  requirements?: GuardRequirements;
}): RouteGuardDecision {
  const { state, params, requirements } = args;

  if (state.status === "loading") {
    return "loading";
  }

  if (state.status === "unauthorized") {
    return "redirect-unauthorized";
  }

  if (state.status === "forbidden") {
    return "redirect-forbidden";
  }

  if (state.status === "error") {
    return "error";
  }

  if (!state.session) {
    return "redirect-unauthorized";
  }

  const scopeResult = buildScopeRequirement(requirements?.requireScope, params);
  if (!scopeResult.hasRequiredContext) {
    return "redirect-forbidden";
  }

  const allowed = canAccessRouteForSession(state.session, {
    roles: requirements?.roles,
    permission: requirements?.permission,
    scope: scopeResult.scope,
  });

  if (!allowed) {
    return "redirect-forbidden";
  }

  return "allow";
}

export function ProtectedRoute({ children, requirements }: ProtectedRouteProps) {
  const { state } = useAuth();
  const params = useParams();
  const decision = evaluateProtectedRouteDecision({ state, params, requirements });

  if (decision === "loading") {
    return <div className="route-guard-state">Loading session context...</div>;
  }

  if (decision === "redirect-unauthorized") {
    return <Navigate to={routePaths.unauthorized} replace />;
  }

  if (decision === "redirect-forbidden") {
    return <Navigate to={routePaths.forbidden} replace />;
  }

  if (decision === "error") {
    return (
      <section>
        <h2>Session initialization error</h2>
        <p>{state.errorMessage}</p>
      </section>
    );
  }

  return <>{children}</>;
}
