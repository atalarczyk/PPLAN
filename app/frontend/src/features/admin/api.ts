import { apiGet, apiPatch, apiPost, type QueryParams } from "../../app/api/http";

export type AppRole = "super_admin" | "business_unit_admin" | "editor" | "viewer";

export interface BusinessUnitRecord {
  id: string;
  code: string;
  name: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

interface BusinessUnitListResponse {
  items: BusinessUnitRecord[];
}

export interface BusinessUnitCreateInput {
  code: string;
  name: string;
  active: boolean;
}

export interface BusinessUnitUpdateInput {
  name?: string;
  active?: boolean;
}

export interface RoleAssignmentRecord {
  id: string;
  user_id: string;
  business_unit_id: string | null;
  role: AppRole;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserRecord {
  id: string;
  microsoft_oid: string;
  email: string;
  display_name: string;
  status: string;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
  role_assignments: RoleAssignmentRecord[];
}

interface UsersResponse {
  items: UserRecord[];
}

export interface RoleAssignmentCreateInput {
  user_email: string;
  user_display_name?: string;
  user_microsoft_oid: string;
  role: AppRole;
  business_unit_id: string | null;
  active: boolean;
}

export interface RoleAssignmentUpdateInput {
  role?: AppRole;
  business_unit_id?: string | null;
  active?: boolean;
}

export interface UserListQuery extends QueryParams {
  business_unit_id?: string;
}

export async function listBusinessUnits(): Promise<BusinessUnitRecord[]> {
  const response = await apiGet<BusinessUnitListResponse>("/business-units");
  return response.items;
}

export async function createBusinessUnit(input: BusinessUnitCreateInput): Promise<BusinessUnitRecord> {
  return apiPost<BusinessUnitRecord>("/business-units", {
    body: input,
  });
}

export async function updateBusinessUnit(
  businessUnitId: string,
  input: BusinessUnitUpdateInput,
): Promise<BusinessUnitRecord> {
  return apiPatch<BusinessUnitRecord>(`/business-units/${businessUnitId}`, {
    body: input,
  });
}

export async function listUsers(query: UserListQuery = {}): Promise<UserRecord[]> {
  const response = await apiGet<UsersResponse>("/users", {
    query,
  });
  return response.items;
}

export async function createRoleAssignment(input: RoleAssignmentCreateInput): Promise<RoleAssignmentRecord> {
  return apiPost<RoleAssignmentRecord>("/users/role-assignments", {
    body: input,
  });
}

export async function updateRoleAssignment(
  assignmentId: string,
  input: RoleAssignmentUpdateInput,
): Promise<RoleAssignmentRecord> {
  return apiPatch<RoleAssignmentRecord>(`/users/role-assignments/${assignmentId}`, {
    body: input,
  });
}

