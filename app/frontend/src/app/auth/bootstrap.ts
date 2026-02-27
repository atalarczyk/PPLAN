import { ApiError } from "../api/http";

import { loadAuthSession } from "./api";
import type { AuthSession, AuthState } from "./types";

function resolveForbiddenMessage(session: AuthSession): string {
  if (!session.hasAccess) {
    return "Your account is authenticated but has no assigned platform access yet.";
  }

  if (session.user.status !== "active") {
    return "Your account is not active in the platform.";
  }

  return "Access to this resource is restricted.";
}

export function deriveAuthStateFromSession(session: AuthSession): AuthState {
  if (!session.hasAccess || session.user.status !== "active") {
    return {
      status: "forbidden",
      session,
      errorMessage: resolveForbiddenMessage(session),
    };
  }

  return {
    status: "authenticated",
    session,
  };
}

export function mapBootstrapError(error: unknown): AuthState {
  if (error instanceof ApiError && error.status === 401) {
    return {
      status: "unauthorized",
      session: null,
      errorMessage: "Authentication is required. Complete sign-in to continue.",
    };
  }

  if (error instanceof ApiError && error.status === 403) {
    return {
      status: "forbidden",
      session: null,
      errorMessage: "Your identity is known, but access is forbidden by policy.",
    };
  }

  return {
    status: "error",
    session: null,
    errorMessage: "Unable to initialize session context from backend endpoints.",
  };
}

export async function bootstrapAuthState(
  loader: () => Promise<AuthSession> = loadAuthSession,
): Promise<AuthState> {
  try {
    const session = await loader();
    return deriveAuthStateFromSession(session);
  } catch (error) {
    return mapBootstrapError(error);
  }
}

