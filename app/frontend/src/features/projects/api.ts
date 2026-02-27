import { apiDelete, apiGet, apiPatch, apiPost } from "../../app/api/http";
import { registerProjectScope, registerProjectScopes } from "../../app/auth/permissions";

export type ProjectStatus = "draft" | "active" | "closed";

export interface ProjectRecord {
  id: string;
  business_unit_id: string;
  code: string;
  name: string;
  description: string | null;
  start_month: string;
  end_month: string;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

interface ProjectListResponse {
  items: ProjectRecord[];
}

export interface ProjectCreateInput {
  code: string;
  name: string;
  description?: string | null;
  start_month: string;
  end_month: string;
  status: ProjectStatus;
}

export interface ProjectUpdateInput {
  code?: string;
  name?: string;
  description?: string | null;
  start_month?: string;
  end_month?: string;
  status?: ProjectStatus;
}

export interface StageRecord {
  id: string;
  project_id: string;
  name: string;
  start_month: string;
  end_month: string;
  color_token: string;
  sequence_no: number;
}

interface StageListResponse {
  items: StageRecord[];
}

export interface StageCreateInput {
  name: string;
  start_month: string;
  end_month: string;
  color_token: string;
  sequence_no: number;
}

export interface StageUpdateInput {
  name?: string;
  start_month?: string;
  end_month?: string;
  color_token?: string;
  sequence_no?: number;
}

export interface TaskRecord {
  id: string;
  project_id: string;
  stage_id: string;
  code: string;
  name: string;
  sequence_no: number;
  active: boolean;
}

interface TaskListResponse {
  items: TaskRecord[];
}

export interface TaskCreateInput {
  stage_id: string;
  code: string;
  name: string;
  sequence_no: number;
  active: boolean;
}

export interface TaskUpdateInput {
  stage_id?: string;
  code?: string;
  name?: string;
  sequence_no?: number;
  active?: boolean;
}

export interface PerformerRecord {
  id: string;
  business_unit_id: string;
  external_ref: string | null;
  display_name: string;
  active: boolean;
}

interface PerformerListResponse {
  items: PerformerRecord[];
}

export interface PerformerCreateInput {
  external_ref?: string | null;
  display_name: string;
  active: boolean;
}

export interface PerformerUpdateInput {
  external_ref?: string | null;
  display_name?: string;
  active?: boolean;
}

export interface TaskPerformerAssignmentRecord {
  task_id: string;
  performer_id: string;
}

interface AssignmentListResponse {
  items: TaskPerformerAssignmentRecord[];
}

export interface TaskPerformerAssignmentCreateInput {
  task_id: string;
  performer_id: string;
}

export async function listBusinessUnitProjects(businessUnitId: string): Promise<ProjectRecord[]> {
  const response = await apiGet<ProjectListResponse>(`/business-units/${businessUnitId}/projects`);
  registerProjectScopes(response.items);
  return response.items;
}

export async function createBusinessUnitProject(
  businessUnitId: string,
  input: ProjectCreateInput,
): Promise<ProjectRecord> {
  const created = await apiPost<ProjectRecord>(`/business-units/${businessUnitId}/projects`, {
    body: input,
  });
  registerProjectScope(created.id, created.business_unit_id);
  return created;
}

export async function getProject(projectId: string): Promise<ProjectRecord> {
  const project = await apiGet<ProjectRecord>(`/projects/${projectId}`);
  registerProjectScope(project.id, project.business_unit_id);
  return project;
}

export async function updateProject(projectId: string, input: ProjectUpdateInput): Promise<ProjectRecord> {
  const project = await apiPatch<ProjectRecord>(`/projects/${projectId}`, {
    body: input,
  });
  registerProjectScope(project.id, project.business_unit_id);
  return project;
}

export async function deleteProject(projectId: string): Promise<void> {
  await apiDelete(`/projects/${projectId}`);
}

export async function listProjectStages(projectId: string): Promise<StageRecord[]> {
  const response = await apiGet<StageListResponse>(`/projects/${projectId}/stages`);
  return response.items;
}

export async function createProjectStage(projectId: string, input: StageCreateInput): Promise<StageRecord> {
  return apiPost<StageRecord>(`/projects/${projectId}/stages`, {
    body: input,
  });
}

export async function updateProjectStage(
  projectId: string,
  stageId: string,
  input: StageUpdateInput,
): Promise<StageRecord> {
  return apiPatch<StageRecord>(`/projects/${projectId}/stages/${stageId}`, {
    body: input,
  });
}

export async function deleteProjectStage(projectId: string, stageId: string): Promise<void> {
  await apiDelete(`/projects/${projectId}/stages/${stageId}`);
}

export async function listProjectTasks(projectId: string): Promise<TaskRecord[]> {
  const response = await apiGet<TaskListResponse>(`/projects/${projectId}/tasks`);
  return response.items;
}

export async function createProjectTask(projectId: string, input: TaskCreateInput): Promise<TaskRecord> {
  return apiPost<TaskRecord>(`/projects/${projectId}/tasks`, {
    body: input,
  });
}

export async function updateProjectTask(
  projectId: string,
  taskId: string,
  input: TaskUpdateInput,
): Promise<TaskRecord> {
  return apiPatch<TaskRecord>(`/projects/${projectId}/tasks/${taskId}`, {
    body: input,
  });
}

export async function deleteProjectTask(projectId: string, taskId: string): Promise<void> {
  await apiDelete(`/projects/${projectId}/tasks/${taskId}`);
}

export async function listProjectPerformers(projectId: string): Promise<PerformerRecord[]> {
  const response = await apiGet<PerformerListResponse>(`/projects/${projectId}/performers`);
  return response.items;
}

export async function createProjectPerformer(
  projectId: string,
  input: PerformerCreateInput,
): Promise<PerformerRecord> {
  return apiPost<PerformerRecord>(`/projects/${projectId}/performers`, {
    body: input,
  });
}

export async function updateProjectPerformer(
  projectId: string,
  performerId: string,
  input: PerformerUpdateInput,
): Promise<PerformerRecord> {
  return apiPatch<PerformerRecord>(`/projects/${projectId}/performers/${performerId}`, {
    body: input,
  });
}

export async function deleteProjectPerformer(projectId: string, performerId: string): Promise<void> {
  await apiDelete(`/projects/${projectId}/performers/${performerId}`);
}

export async function listTaskPerformerAssignments(projectId: string): Promise<TaskPerformerAssignmentRecord[]> {
  const response = await apiGet<AssignmentListResponse>(`/projects/${projectId}/task-performer-assignments`);
  return response.items;
}

export async function createTaskPerformerAssignment(
  projectId: string,
  input: TaskPerformerAssignmentCreateInput,
): Promise<TaskPerformerAssignmentRecord> {
  return apiPost<TaskPerformerAssignmentRecord>(`/projects/${projectId}/task-performer-assignments`, {
    body: input,
  });
}

export async function deleteTaskPerformerAssignment(
  projectId: string,
  taskId: string,
  performerId: string,
): Promise<void> {
  await apiDelete(`/projects/${projectId}/task-performer-assignments/${taskId}/${performerId}`);
}

