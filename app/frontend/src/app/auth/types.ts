export const APP_ROLES = ["super_admin", "business_unit_admin", "editor", "viewer"] as const;

export type AppRole = (typeof APP_ROLES)[number];

export interface RoleAssignment {
  role: AppRole;
  businessUnitId: string | null;
}

export interface AuthUserProfile {
  id: string;
  email: string;
  displayName: string;
  status: string;
  microsoftOid: string;
}

export interface AuthSession {
  user: AuthUserProfile;
  roles: AppRole[];
  assignments: RoleAssignment[];
  businessUnitIds: string[];
  hasAccess: boolean;
}

export type AuthStatus = "loading" | "authenticated" | "unauthorized" | "forbidden" | "error";

export interface AuthState {
  status: AuthStatus;
  session: AuthSession | null;
  errorMessage?: string;
}

export function isAppRole(value: string): value is AppRole {
  return APP_ROLES.includes(value as AppRole);
}

