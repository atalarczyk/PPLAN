import { apiGet, apiPost, apiPut, type QueryParams } from "../../app/api/http";

export type RateUnit = "day" | "fte_month";
export type MoneyCurrency = "PLN" | "EUR" | "USD";

export interface RateEntryRecord {
  id: string;
  business_unit_id: string;
  performer_id: string;
  project_id: string | null;
  rate_unit: RateUnit;
  rate_value: string;
  effective_from_month: string;
  effective_to_month: string | null;
}

interface RatesResponse {
  items: RateEntryRecord[];
}

export interface RateEntryInput {
  performer_id: string;
  project_id?: string | null;
  rate_unit: RateUnit;
  rate_value: string;
  effective_from_month: string;
  effective_to_month?: string | null;
}

export interface RatesBulkUpsertResult {
  updated_entries: number;
  items: RateEntryRecord[];
}

export interface FinancialRequestRecord {
  id: string;
  project_id: string;
  request_no: string;
  request_date: string;
  month_start: string;
  amount: string;
  currency: MoneyCurrency;
  status: string;
}

interface FinancialRequestsResponse {
  items: FinancialRequestRecord[];
}

export interface FinancialRequestCreateInput {
  request_no: string;
  request_date: string;
  month_start: string;
  amount: string;
  currency: MoneyCurrency;
  status: string;
}

export interface InvoiceRecord {
  id: string;
  project_id: string;
  invoice_no: string;
  invoice_date: string;
  month_start: string;
  amount: string;
  currency: MoneyCurrency;
  payment_status: string;
  payment_date: string | null;
}

interface InvoicesResponse {
  items: InvoiceRecord[];
}

export interface InvoiceCreateInput {
  invoice_no: string;
  invoice_date: string;
  month_start: string;
  amount: string;
  currency: MoneyCurrency;
  payment_status: string;
  payment_date?: string | null;
}

export interface RevenueRecord {
  id: string;
  project_id: string;
  revenue_no: string;
  recognition_date: string;
  month_start: string;
  amount: string;
  currency: MoneyCurrency;
}

interface RevenuesResponse {
  items: RevenueRecord[];
}

export interface RevenueCreateInput {
  revenue_no: string;
  recognition_date: string;
  month_start: string;
  amount: string;
  currency: MoneyCurrency;
}

export interface FinanceSummaryMonth {
  month_start: string;
  planned_person_days: string;
  actual_person_days: string;
  planned_cost: string;
  actual_cost: string;
  invoice_amount: string;
  revenue_amount: string;
  cumulative_planned_cost: string;
  cumulative_actual_cost: string;
  cumulative_revenue: string;
}

export interface FinanceSummaryPayload {
  project_id: string;
  from_month: string;
  to_month: string;
  months: FinanceSummaryMonth[];
}

export interface FinanceSummaryQuery extends QueryParams {
  from_month?: string;
  to_month?: string;
}

export async function listProjectRates(projectId: string): Promise<RateEntryRecord[]> {
  const response = await apiGet<RatesResponse>(`/projects/${projectId}/rates`);
  return response.items;
}

export async function bulkUpsertProjectRates(
  projectId: string,
  entries: RateEntryInput[],
): Promise<RatesBulkUpsertResult> {
  return apiPut<RatesBulkUpsertResult>(`/projects/${projectId}/rates/entries/bulk`, {
    body: { entries },
  });
}

export async function getProjectFinanceSummary(
  projectId: string,
  query: FinanceSummaryQuery = {},
): Promise<FinanceSummaryPayload> {
  return apiGet<FinanceSummaryPayload>(`/projects/${projectId}/finance-summary`, {
    query,
  });
}

export async function listProjectFinancialRequests(projectId: string): Promise<FinancialRequestRecord[]> {
  const response = await apiGet<FinancialRequestsResponse>(`/projects/${projectId}/financial-requests`);
  return response.items;
}

export async function createProjectFinancialRequest(
  projectId: string,
  input: FinancialRequestCreateInput,
): Promise<FinancialRequestRecord> {
  return apiPost<FinancialRequestRecord>(`/projects/${projectId}/financial-requests`, {
    body: input,
  });
}

export async function listProjectInvoices(projectId: string): Promise<InvoiceRecord[]> {
  const response = await apiGet<InvoicesResponse>(`/projects/${projectId}/invoices`);
  return response.items;
}

export async function createProjectInvoice(projectId: string, input: InvoiceCreateInput): Promise<InvoiceRecord> {
  return apiPost<InvoiceRecord>(`/projects/${projectId}/invoices`, {
    body: input,
  });
}

export async function listProjectRevenues(projectId: string): Promise<RevenueRecord[]> {
  const response = await apiGet<RevenuesResponse>(`/projects/${projectId}/revenues`);
  return response.items;
}

export async function createProjectRevenue(projectId: string, input: RevenueCreateInput): Promise<RevenueRecord> {
  return apiPost<RevenueRecord>(`/projects/${projectId}/revenues`, {
    body: input,
  });
}

