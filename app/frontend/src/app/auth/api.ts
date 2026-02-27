import { ApiError, apiGet } from "../api/http";
import { AuthSession, isAppRole, type AppRole, type AuthUserProfile, type RoleAssignment } from "./types";

interface MeApiResponse {
  id: string;
  microsoft_oid: string;
  email: string;
  display_name: string;
  status: string;
  roles: Array<{
    role: string;
    business_unit_id: string | null;
  }>;
}

interface AccessContextApiResponse {
  user: {
    id: string;
    email: string;
    display_name: string;
    status: string;
    microsoft_oid: string;
  };
  roles: string[];
  assignments: Array<{
    role: string;
    business_unit_id: string | null;
  }>;
  business_units: string[];
  has_access: boolean;
}

function toAppRole(role: string): AppRole | null {
  return isAppRole(role) ? role : null;
}

function mapAssignments(
  assignments: Array<{ role: string; business_unit_id: string | null }>,
): RoleAssignment[] {
  const mapped: RoleAssignment[] = [];

  for (const assignment of assignments) {
    const role = toAppRole(assignment.role);
    if (!role) {
      continue;
    }

    mapped.push({
      role,
      businessUnitId: assignment.business_unit_id,
    });
  }

  return mapped;
}

function mapRoles(roles: string[]): AppRole[] {
  const normalized = roles
    .map((role) => toAppRole(role))
    .filter((role): role is AppRole => role !== null);

  return Array.from(new Set(normalized));
}

function toUserProfile(payload: AccessContextApiResponse["user"]): AuthUserProfile {
  return {
    id: payload.id,
    email: payload.email,
    displayName: payload.display_name,
    status: payload.status,
    microsoftOid: payload.microsoft_oid,
  };
}

function createSession(accessContext: AccessContextApiResponse): AuthSession {
  return {
    user: toUserProfile(accessContext.user),
    roles: mapRoles(accessContext.roles),
    assignments: mapAssignments(accessContext.assignments),
    businessUnitIds: accessContext.business_units,
    hasAccess: accessContext.has_access,
  };
}

function normalizeFromMeFallback(me: MeApiResponse): AuthSession {
  const assignments = mapAssignments(me.roles);
  const roles = Array.from(new Set(assignments.map((assignment) => assignment.role)));
  const businessUnitIds = Array.from(
    new Set(
      assignments
        .map((assignment) => assignment.businessUnitId)
        .filter((businessUnitId): businessUnitId is string => businessUnitId !== null),
    ),
  );

  return {
    user: {
      id: me.id,
      email: me.email,
      displayName: me.display_name,
      status: me.status,
      microsoftOid: me.microsoft_oid,
    },
    roles,
    assignments,
    businessUnitIds,
    hasAccess: assignments.length > 0,
  };
}

export async function loadAuthSession(): Promise<AuthSession> {
  try {
    const accessContext = await apiGet<AccessContextApiResponse>("/access/context");
    return createSession(accessContext);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      const mePayload = await apiGet<MeApiResponse>("/me");
      return normalizeFromMeFallback(mePayload);
    }
    throw error;
  }
}

