import { describe, expect, it } from "vitest";

import { buildPrimaryNavigation } from "../app/navigation";
import type { AuthSession } from "../app/auth/types";

function createSession(overrides?: Partial<AuthSession>): AuthSession {
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
    ...overrides,
  };
}

describe("permission-aware navigation", () => {
  it("shows projects and BU dashboard for viewer", () => {
    const items = buildPrimaryNavigation(createSession());
    const keys = items.map((item) => item.key);

    expect(keys).toContain("projects");
    expect(keys).toContain("business-unit-dashboard");
    expect(keys).not.toContain("admin");
  });

  it("shows admin entry for business-unit admin", () => {
    const items = buildPrimaryNavigation(
      createSession({
        roles: ["business_unit_admin"],
        assignments: [{ role: "business_unit_admin", businessUnitId: "11111111-1111-1111-1111-111111111111" }],
      }),
    );
    const keys = items.map((item) => item.key);

    expect(keys).toContain("admin");
  });

  it("marks BU dashboard as disabled when no scoped business unit exists", () => {
    const items = buildPrimaryNavigation(
      createSession({
        roles: ["super_admin"],
        assignments: [{ role: "super_admin", businessUnitId: null }],
        businessUnitIds: [],
      }),
    );

    const buDashboard = items.find((item) => item.key === "business-unit-dashboard");
    expect(buDashboard).toBeDefined();
    expect(buDashboard?.enabled).toBe(false);
  });
});

