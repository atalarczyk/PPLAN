import { apiGet, type QueryParams } from "../../app/api/http";

export interface CostTrendPoint {
  month_start: string;
  planned_cost: string;
  actual_cost: string;
  cumulative_planned_cost: string;
  cumulative_actual_cost: string;
}

export interface ProjectWorkloadPoint {
  month_start: string;
  planned_person_days: string;
  actual_person_days: string;
}

export interface ProjectWorkloadSeries {
  performer_id: string;
  performer_name: string;
  months: ProjectWorkloadPoint[];
}

export interface RealizationTrendPoint {
  month_start: string;
  cumulative_revenue: string;
  cumulative_actual_cost: string;
  cumulative_margin: string;
  realization_percent: string;
}

export interface ProjectDashboardPayload {
  scope: "project";
  project_id: string;
  from_month: string;
  to_month: string;
  cumulative_cost_trend: CostTrendPoint[];
  workload_trend: ProjectWorkloadSeries[];
  realization_trend: RealizationTrendPoint[];
}

export interface BusinessUnitWorkloadSeries {
  performer_id: string;
  performer_name: string;
  months: ProjectWorkloadPoint[];
}

export interface BusinessUnitDashboardPayload {
  scope: "business_unit";
  business_unit_id: string;
  from_month: string | null;
  to_month: string | null;
  aggregated_cumulative_cost_trend: CostTrendPoint[];
  workload_heatmap: BusinessUnitWorkloadSeries[];
  realization_trend: RealizationTrendPoint[];
}

export interface DashboardQuery extends QueryParams {
  from_month?: string;
  to_month?: string;
}

export async function getProjectDashboard(
  projectId: string,
  query: DashboardQuery = {},
): Promise<ProjectDashboardPayload> {
  return apiGet<ProjectDashboardPayload>(`/dashboards/projects/${projectId}`, {
    query,
  });
}

export async function getBusinessUnitDashboard(
  businessUnitId: string,
  query: DashboardQuery = {},
): Promise<BusinessUnitDashboardPayload> {
  return apiGet<BusinessUnitDashboardPayload>(`/dashboards/business-units/${businessUnitId}`, {
    query,
  });
}

