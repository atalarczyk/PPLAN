import { describe, expect, it } from "vitest";

import { evaluateProtectedRouteDecision } from "../app/auth/routeGuards";
import { clearProjectScopeRegistry, registerProjectScope } from "../app/auth/permissions";
import type { AuthState } from "../app/auth/types";

function authenticatedState(overrides?: Partial<AuthState>): AuthState {
  return {
    status: "authenticated",
    session: {
      user: {
        id: "u-1",
        email: "editor@test.local",
        displayName: "Editor",
        status: "active",
        microsoftOid: "oid-1",
      },
      roles: ["editor"],
      assignments: [{ role: "editor", businessUnitId: "11111111-1111-1111-1111-111111111111" }],
      businessUnitIds: ["11111111-1111-1111-1111-111111111111"],
      hasAccess: true,
    },
    ...overrides,
  };
}

describe("route guards", () => {
  it("allows project scoped route when project scope is registered", () => {
    clearProjectScopeRegistry();
    registerProjectScope("22222222-2222-2222-2222-222222222222", "11111111-1111-1111-1111-111111111111");

    const decision = evaluateProtectedRouteDecision({
      state: authenticatedState(),
      params: { projectId: "22222222-2222-2222-2222-222222222222" },
      requirements: {
        permission: "finance.edit",
        requireScope: "project",
      },
    });

    expect(decision).toBe("allow");
  });

  it("forbids project scoped route when project resolves to foreign business unit", () => {
    clearProjectScopeRegistry();
    registerProjectScope("22222222-2222-2222-2222-222222222222", "99999999-9999-9999-9999-999999999999");

    const decision = evaluateProtectedRouteDecision({
      state: authenticatedState(),
      params: { projectId: "22222222-2222-2222-2222-222222222222" },
      requirements: {
        permission: "finance.edit",
        requireScope: "project",
      },
    });

    expect(decision).toBe("redirect-forbidden");
  });

  it("redirects unauthorized status to unauthorized route", () => {
    const decision = evaluateProtectedRouteDecision({
      state: { status: "unauthorized", session: null },
      params: {},
    });

    expect(decision).toBe("redirect-unauthorized");
  });

  it("allows editor on project reports route with scope context", () => {
    clearProjectScopeRegistry();
    registerProjectScope("22222222-2222-2222-2222-222222222222", "11111111-1111-1111-1111-111111111111");

    const decision = evaluateProtectedRouteDecision({
      state: authenticatedState(),
      params: { projectId: "22222222-2222-2222-2222-222222222222" },
      requirements: {
        permission: "reports.view",
        requireScope: "project",
      },
    });

    expect(decision).toBe("allow");
  });

  it("forbids viewer on finance editing route", () => {
    const decision = evaluateProtectedRouteDecision({
      state: authenticatedState({
        session: {
          ...authenticatedState().session!,
          roles: ["viewer"],
          assignments: [{ role: "viewer", businessUnitId: "11111111-1111-1111-1111-111111111111" }],
        },
      }),
      params: { projectId: "22222222-2222-2222-2222-222222222222" },
      requirements: {
        permission: "finance.edit",
        requireScope: "project",
      },
    });

    expect(decision).toBe("redirect-forbidden");
  });

  it("forbids business-unit scoped route when required context param is missing", () => {
    const decision = evaluateProtectedRouteDecision({
      state: authenticatedState(),
      params: {},
      requirements: {
        permission: "dashboards.view",
        requireScope: "businessUnit",
      },
    });

    expect(decision).toBe("redirect-forbidden");
  });
});
