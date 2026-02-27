import { apiGet, type QueryParams } from "../../app/api/http";

export type ReportKey = "effort-by-performer" | "effort-by-task" | "cost-by-performer" | "cost-by-task";

export interface ReportRowMonth {
  month_start: string;
  planned?: string;
  actual?: string;
  planned_cost?: string;
  actual_cost?: string;
  variance: string;
}

export interface ReportTotals {
  planned?: string;
  actual?: string;
  planned_cost?: string;
  actual_cost?: string;
  variance: string;
}

export interface ReportRow {
  performer_id?: string;
  performer_name?: string;
  task_id?: string;
  task_name?: string;
  stage_name?: string;
  months: ReportRowMonth[];
  totals: ReportTotals;
}

export interface ReportPayload {
  report_key: ReportKey;
  project_id: string;
  from_month: string;
  to_month: string;
  months: string[];
  rows: ReportRow[];
}

export interface ReportQuery extends QueryParams {
  from_month?: string;
  to_month?: string;
  performer_id?: string[];
  task_id?: string[];
}

const reportPathMap: Record<ReportKey, string> = {
  "effort-by-performer": "effort-by-performer",
  "effort-by-task": "effort-by-task",
  "cost-by-performer": "cost-by-performer",
  "cost-by-task": "cost-by-task",
};

export async function getProjectReport(
  projectId: string,
  reportKey: ReportKey,
  query: ReportQuery = {},
): Promise<ReportPayload> {
  const reportPath = reportPathMap[reportKey];
  return apiGet<ReportPayload>(`/reports/projects/${projectId}/${reportPath}`, {
    query,
  });
}

