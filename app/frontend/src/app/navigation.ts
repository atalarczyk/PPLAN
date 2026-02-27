import { routePaths } from "./routePaths";
import { canAccessRoute, hasPermission } from "./auth/permissions";
import type { AuthSession } from "./auth/types";

export interface NavigationItem {
  key: string;
  label: string;
  to: string;
  enabled: boolean;
  reason?: string;
}

export function buildPrimaryNavigation(session: AuthSession | null): NavigationItem[] {
  const items: NavigationItem[] = [];

  if (hasPermission(session, { permission: "projects.read" })) {
    items.push({
      key: "projects",
      label: "Projects",
      to: routePaths.projects,
      enabled: true,
    });
  }

  if (hasPermission(session, { permission: "dashboards.view" })) {
    const businessUnitId = session?.businessUnitIds[0];
    if (businessUnitId) {
      items.push({
        key: "business-unit-dashboard",
        label: "BU Dashboard",
        to: routePaths.businessUnitDashboard(businessUnitId),
        enabled: true,
      });
    } else {
      items.push({
        key: "business-unit-dashboard",
        label: "BU Dashboard",
        to: routePaths.projects,
        enabled: false,
        reason: "No scoped business unit context available.",
      });
    }
  }

  if (
    canAccessRoute(session, {
      roles: ["super_admin", "business_unit_admin"],
      permission: "admin.view",
    })
  ) {
    items.push({
      key: "admin",
      label: "Admin",
      to: routePaths.admin,
      enabled: true,
    });
  }

  return items;
}

