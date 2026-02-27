import { describe, expect, it, vi } from "vitest";

import { ApiError } from "../app/api/http";
import { bootstrapAuthState, deriveAuthStateFromSession, mapBootstrapError } from "../app/auth/bootstrap";
import type { AuthSession } from "../app/auth/types";

function createSession(partial?: Partial<AuthSession>): AuthSession {
  return {
    user: {
      id: "u-1",
      email: "user@test.local",
      displayName: "User",
      status: "active",
      microsoftOid: "oid-1",
    },
    roles: ["viewer"],
    assignments: [{ role: "viewer", businessUnitId: "11111111-1111-1111-1111-111111111111" }],
    businessUnitIds: ["11111111-1111-1111-1111-111111111111"],
    hasAccess: true,
    ...partial,
  };
}

describe("auth bootstrap", () => {
  it("returns authenticated state for active assigned user", () => {
    const state = deriveAuthStateFromSession(createSession());

    expect(state.status).toBe("authenticated");
    expect(state.session?.user.email).toBe("user@test.local");
  });

  it("returns forbidden state for authenticated user without assignments", () => {
    const state = deriveAuthStateFromSession(
      createSession({
        hasAccess: false,
        roles: [],
        assignments: [],
        businessUnitIds: [],
      }),
    );

    expect(state.status).toBe("forbidden");
    expect(state.errorMessage).toContain("no assigned platform access");
  });

  it("maps unauthorized API errors to unauthorized state", () => {
    const state = mapBootstrapError(new ApiError("unauthorized", 401, { detail: "Missing identity" }));

    expect(state.status).toBe("unauthorized");
    expect(state.session).toBeNull();
  });

  it("maps unknown errors to generic bootstrap error state", () => {
    const state = mapBootstrapError(new Error("network down"));

    expect(state.status).toBe("error");
    expect(state.errorMessage).toContain("Unable to initialize");
  });

  it("bootstraps with provided loader", async () => {
    const loader = vi.fn().mockResolvedValue(createSession({ roles: ["editor"], assignments: [{ role: "editor", businessUnitId: "11111111-1111-1111-1111-111111111111" }] }));

    const state = await bootstrapAuthState(loader);

    expect(loader).toHaveBeenCalledTimes(1);
    expect(state.status).toBe("authenticated");
    expect(state.session?.roles).toEqual(["editor"]);
  });
});

