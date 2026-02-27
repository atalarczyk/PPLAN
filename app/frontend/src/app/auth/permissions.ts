import type { AppRole, AuthSession, RoleAssignment } from "./types";

export type PermissionKey =
  | "projects.read"
  | "projects.write"
  | "matrix.edit"
  | "finance.edit"
  | "reports.view"
  | "reports.export"
  | "dashboards.view"
  | "admin.view"
  | "admin.assignRoles";

const ROLE_PERMISSION_MAP: Record<AppRole, PermissionKey[]> = {
  super_admin: [
    "projects.read",
    "projects.write",
    "matrix.edit",
    "finance.edit",
    "reports.view",
    "reports.export",
    "dashboards.view",
    "admin.view",
    "admin.assignRoles",
  ],
  business_unit_admin: [
    "projects.read",
    "projects.write",
    "matrix.edit",
    "finance.edit",
    "reports.view",
    "reports.export",
    "dashboards.view",
    "admin.view",
    "admin.assignRoles",
  ],
  editor: [
    "projects.read",
    "projects.write",
    "matrix.edit",
    "finance.edit",
    "reports.view",
    "reports.export",
    "dashboards.view",
  ],
  viewer: ["projects.read", "reports.view", "reports.export", "dashboards.view"],
};

const projectScopeRegistry = new Map<string, string>();

export function registerProjectScope(projectId: string, businessUnitId: string): void {
  const normalizedProjectId = projectId.trim();
  const normalizedBusinessUnitId = businessUnitId.trim();
  if (!normalizedProjectId || !normalizedBusinessUnitId) {
    return;
  }

  projectScopeRegistry.set(normalizedProjectId, normalizedBusinessUnitId);
}

export function registerProjectScopes(
  projects: Array<{ id: string; business_unit_id: string }> | Array<{ id: string; businessUnitId: string }>,
): void {
  for (const project of projects) {
    if ("business_unit_id" in project) {
      registerProjectScope(project.id, project.business_unit_id);
      continue;
    }

    registerProjectScope(project.id, project.businessUnitId);
  }
}

export function clearProjectScopeRegistry(): void {
  projectScopeRegistry.clear();
}

export interface ScopeRequirement {
  businessUnitId?: string;
  projectId?: string;
}

interface PermissionCheckOptions {
  permission: PermissionKey;
  scope?: ScopeRequirement;
}

function isUuidLike(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(value);
}

export function inferBusinessUnitIdFromRouteParams(
  params: Readonly<Record<string, string | undefined>>,
): string | undefined {
  if (params.businessUnitId && isUuidLike(params.businessUnitId)) {
    return params.businessUnitId;
  }

  const projectId = params.projectId;
  if (!projectId || !isUuidLike(projectId)) {
    return undefined;
  }

  return projectScopeRegistry.get(projectId);
}

export function hasRole(session: AuthSession | null, allowedRoles: readonly AppRole[]): boolean {
  if (!session) {
    return false;
  }

  return allowedRoles.some((role) => session.roles.includes(role));
}

function hasPermissionViaAssignment(
  assignments: RoleAssignment[],
  permission: PermissionKey,
  businessUnitId?: string,
): boolean {
  for (const assignment of assignments) {
    if (!ROLE_PERMISSION_MAP[assignment.role].includes(permission)) {
      continue;
    }

    if (assignment.role === "super_admin") {
      return true;
    }

    if (!businessUnitId) {
      return true;
    }

    if (assignment.businessUnitId === businessUnitId) {
      return true;
    }
  }

  return false;
}

function resolveScopeBusinessUnitId(session: AuthSession, scope?: ScopeRequirement): string | undefined {
  if (!scope) {
    return undefined;
  }

  if (scope.businessUnitId) {
    return scope.businessUnitId;
  }

  if (scope.projectId) {
    const resolved = projectScopeRegistry.get(scope.projectId);
    if (resolved) {
      return resolved;
    }

    if (session.businessUnitIds.length === 1) {
      return session.businessUnitIds[0];
    }

    return undefined;
  }

  // fall back to first scoped BU for generic scoped pages if available.
  return session.businessUnitIds[0];
}

export function hasPermission(session: AuthSession | null, options: PermissionCheckOptions): boolean {
  if (!session || !session.hasAccess) {
    return false;
  }

  const scopeBusinessUnitId = resolveScopeBusinessUnitId(session, options.scope);
  return hasPermissionViaAssignment(session.assignments, options.permission, scopeBusinessUnitId);
}

export function canAccessRoute(
  session: AuthSession | null,
  requirements: {
    roles?: AppRole[];
    permission?: PermissionKey;
    scope?: ScopeRequirement;
  },
): boolean {
  if (!session) {
    return false;
  }

  if (requirements.roles && requirements.roles.length > 0 && !hasRole(session, requirements.roles)) {
    return false;
  }

  if (requirements.permission && !hasPermission(session, { permission: requirements.permission, scope: requirements.scope })) {
    return false;
  }

  return true;
}
