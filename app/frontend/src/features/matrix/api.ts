import { apiGet, apiPut, type QueryParams } from "../../app/api/http";

interface ProjectSummary {
  id: string;
  business_unit_id: string;
  code: string;
  name: string;
  description: string | null;
  start_month: string;
  end_month: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface MatrixStageRow {
  id: string;
  project_id: string;
  name: string;
  start_month: string;
  end_month: string;
  color_token: string;
  sequence_no: number;
}

interface MatrixTaskMonthlyTotal {
  month_start: string;
  planned_person_days: string;
  actual_person_days: string;
}

export interface MatrixTaskRow {
  id: string;
  project_id: string;
  stage_id: string;
  code: string;
  name: string;
  sequence_no: number;
  active: boolean;
  monthly_totals: MatrixTaskMonthlyTotal[];
  performer_ids: string[];
}

interface MatrixPerformerMonthlyTotal {
  month_start: string;
  planned_person_days: string;
  actual_person_days: string;
}

export interface MatrixPerformerRow {
  id: string;
  business_unit_id: string;
  external_ref: string | null;
  display_name: string;
  active: boolean;
  monthly_totals: MatrixPerformerMonthlyTotal[];
}

export interface MatrixAssignment {
  task_id: string;
  performer_id: string;
}

export interface MatrixEntry {
  task_id: string;
  performer_id: string;
  month_start: string;
  planned_person_days: string;
  actual_person_days: string;
}

export interface MatrixSnapshot {
  month_start: string;
  planned_person_days: string;
  actual_person_days: string;
  planned_cost: string;
  actual_cost: string;
  revenue_amount: string;
  invoice_amount: string;
  cumulative_planned_cost: string;
  cumulative_actual_cost: string;
  cumulative_revenue: string;
}

export interface MatrixPayload {
  project: ProjectSummary;
  months: string[];
  stages: MatrixStageRow[];
  tasks: MatrixTaskRow[];
  performers: MatrixPerformerRow[];
  assignments: MatrixAssignment[];
  entries: MatrixEntry[];
  project_monthly_snapshots: MatrixSnapshot[];
}

export interface MatrixBulkEntryInput {
  task_id: string;
  performer_id: string;
  month_start: string;
  planned_person_days: string;
  actual_person_days: string;
}

export interface MatrixBulkUpsertResult {
  updated_entries: number;
  project_monthly_snapshots: MatrixSnapshot[];
}

export interface MatrixQuery extends QueryParams {
  from_month?: string;
  to_month?: string;
}

export async function getProjectMatrix(projectId: string, query: MatrixQuery = {}): Promise<MatrixPayload> {
  return apiGet<MatrixPayload>(`/projects/${projectId}/matrix`, {
    query,
  });
}

export async function bulkUpsertMatrixEntries(
  projectId: string,
  entries: MatrixBulkEntryInput[],
): Promise<MatrixBulkUpsertResult> {
  return apiPut<MatrixBulkUpsertResult>(`/projects/${projectId}/matrix/entries/bulk`, {
    body: { entries },
  });
}
