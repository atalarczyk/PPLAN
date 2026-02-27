import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";

import { useAuth } from "../../app/auth/AuthProvider";
import { toErrorMessage } from "../shared/errors";
import {
  bulkUpsertProjectRates,
  createProjectFinancialRequest,
  createProjectInvoice,
  createProjectRevenue,
  getProjectFinanceSummary,
  listProjectFinancialRequests,
  listProjectInvoices,
  listProjectRates,
  listProjectRevenues,
  type FinancialRequestRecord,
  type InvoiceRecord,
  type MoneyCurrency,
  type RateEntryRecord,
  type RateUnit,
  type RevenueRecord,
} from "./api";
import { listProjectPerformers, type PerformerRecord } from "../projects/api";

interface RateDraft {
  performer_id: string;
  project_id: string | null;
  rate_unit: RateUnit;
  rate_value: string;
  effective_from_month: string;
  effective_to_month: string;
}

interface FinancialRequestDraft {
  request_no: string;
  request_date: string;
  month_start: string;
  amount: string;
  currency: MoneyCurrency;
  status: string;
}

interface InvoiceDraft {
  invoice_no: string;
  invoice_date: string;
  month_start: string;
  amount: string;
  currency: MoneyCurrency;
  payment_status: string;
  payment_date: string;
}

interface RevenueDraft {
  revenue_no: string;
  recognition_date: string;
  month_start: string;
  amount: string;
  currency: MoneyCurrency;
}

const DEFAULT_RATE_DRAFT: RateDraft = {
  performer_id: "",
  project_id: null,
  rate_unit: "day",
  rate_value: "0.00",
  effective_from_month: "",
  effective_to_month: "",
};

const DEFAULT_FINANCIAL_REQUEST_DRAFT: FinancialRequestDraft = {
  request_no: "",
  request_date: "",
  month_start: "",
  amount: "0.00",
  currency: "PLN",
  status: "draft",
};

const DEFAULT_INVOICE_DRAFT: InvoiceDraft = {
  invoice_no: "",
  invoice_date: "",
  month_start: "",
  amount: "0.00",
  currency: "PLN",
  payment_status: "unpaid",
  payment_date: "",
};

const DEFAULT_REVENUE_DRAFT: RevenueDraft = {
  revenue_no: "",
  recognition_date: "",
  month_start: "",
  amount: "0.00",
  currency: "PLN",
};

function money(total: string): string {
  const number = Number(total);
  return Number.isFinite(number) ? number.toFixed(2) : total;
}

export function FinancePage() {
  const { projectId } = useParams();
  const { hasPermission } = useAuth();

  const [performers, setPerformers] = useState<PerformerRecord[]>([]);
  const [rates, setRates] = useState<RateEntryRecord[]>([]);
  const [requests, setRequests] = useState<FinancialRequestRecord[]>([]);
  const [invoices, setInvoices] = useState<InvoiceRecord[]>([]);
  const [revenues, setRevenues] = useState<RevenueRecord[]>([]);
  const [summaryMonths, setSummaryMonths] = useState<
    Array<{
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
    }>
  >([]);

  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [rateDraft, setRateDraft] = useState<RateDraft>(DEFAULT_RATE_DRAFT);
  const [requestDraft, setRequestDraft] = useState<FinancialRequestDraft>(DEFAULT_FINANCIAL_REQUEST_DRAFT);
  const [invoiceDraft, setInvoiceDraft] = useState<InvoiceDraft>(DEFAULT_INVOICE_DRAFT);
  const [revenueDraft, setRevenueDraft] = useState<RevenueDraft>(DEFAULT_REVENUE_DRAFT);

  const canWrite = projectId ? hasPermission("finance.edit", { projectId }) : false;

  const totals = useMemo(() => {
    const last = summaryMonths.length > 0 ? summaryMonths[summaryMonths.length - 1] : undefined;
    if (!last) {
      return {
        cumulativePlannedCost: "0.00",
        cumulativeActualCost: "0.00",
        cumulativeRevenue: "0.00",
      };
    }

    return {
      cumulativePlannedCost: money(last.cumulative_planned_cost),
      cumulativeActualCost: money(last.cumulative_actual_cost),
      cumulativeRevenue: money(last.cumulative_revenue),
    };
  }, [summaryMonths]);

  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      if (!projectId) {
        setLoading(false);
        setErrorMessage("Missing project route parameter.");
        return;
      }

      setLoading(true);
      setErrorMessage(null);

      try {
        const [performerRows, rateRows, requestRows, invoiceRows, revenueRows, summaryPayload] = await Promise.all([
          listProjectPerformers(projectId),
          listProjectRates(projectId),
          listProjectFinancialRequests(projectId),
          listProjectInvoices(projectId),
          listProjectRevenues(projectId),
          getProjectFinanceSummary(projectId),
        ]);

        if (cancelled) {
          return;
        }

        setPerformers(performerRows);
        setRates(rateRows);
        setRequests(requestRows);
        setInvoices(invoiceRows);
        setRevenues(revenueRows);
        setSummaryMonths(summaryPayload.months);

        const firstPerformer = performerRows[0]?.id ?? "";
        setRateDraft((previous) => ({
          ...previous,
          performer_id: previous.performer_id || firstPerformer,
          project_id: previous.project_id ?? projectId,
          effective_from_month:
            previous.effective_from_month || summaryPayload.from_month || new Date().toISOString().slice(0, 10),
        }));

        const fromMonth = summaryPayload.from_month || new Date().toISOString().slice(0, 10);
        setRequestDraft((previous) => ({
          ...previous,
          request_date: previous.request_date || fromMonth,
          month_start: previous.month_start || fromMonth,
        }));
        setInvoiceDraft((previous) => ({
          ...previous,
          invoice_date: previous.invoice_date || fromMonth,
          month_start: previous.month_start || fromMonth,
        }));
        setRevenueDraft((previous) => ({
          ...previous,
          recognition_date: previous.recognition_date || fromMonth,
          month_start: previous.month_start || fromMonth,
        }));
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(toErrorMessage(error, "Unable to load finance data."));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadData();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  async function refresh(): Promise<void> {
    if (!projectId) {
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      const [rateRows, requestRows, invoiceRows, revenueRows, summaryPayload] = await Promise.all([
        listProjectRates(projectId),
        listProjectFinancialRequests(projectId),
        listProjectInvoices(projectId),
        listProjectRevenues(projectId),
        getProjectFinanceSummary(projectId),
      ]);
      setRates(rateRows);
      setRequests(requestRows);
      setInvoices(invoiceRows);
      setRevenues(revenueRows);
      setSummaryMonths(summaryPayload.months);
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to refresh finance data."));
    } finally {
      setLoading(false);
    }
  }

  async function onAddRate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId || !canWrite) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const result = await bulkUpsertProjectRates(projectId, [
        {
          performer_id: rateDraft.performer_id,
          project_id: rateDraft.project_id,
          rate_unit: rateDraft.rate_unit,
          rate_value: rateDraft.rate_value,
          effective_from_month: rateDraft.effective_from_month,
          effective_to_month: rateDraft.effective_to_month || null,
        },
      ]);
      await refresh();
      setSuccessMessage(`Rate upsert completed (${result.updated_entries} entry).`);
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to save rate."));
    }
  }

  async function onCreateRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId || !canWrite) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await createProjectFinancialRequest(projectId, requestDraft);
      setRequestDraft((previous) => ({
        ...previous,
        request_no: "",
        amount: "0.00",
      }));
      await refresh();
      setSuccessMessage("Financial request created.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to create financial request."));
    }
  }

  async function onCreateInvoice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId || !canWrite) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await createProjectInvoice(projectId, {
        ...invoiceDraft,
        payment_date: invoiceDraft.payment_date || null,
      });
      setInvoiceDraft((previous) => ({
        ...previous,
        invoice_no: "",
        amount: "0.00",
      }));
      await refresh();
      setSuccessMessage("Invoice created.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to create invoice."));
    }
  }

  async function onCreateRevenue(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId || !canWrite) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await createProjectRevenue(projectId, revenueDraft);
      setRevenueDraft((previous) => ({
        ...previous,
        revenue_no: "",
        amount: "0.00",
      }));
      await refresh();
      setSuccessMessage("Revenue created.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to create revenue."));
    }
  }

  if (!projectId) {
    return (
      <section>
        <h2>Finance</h2>
        <p className="app-state app-error">Missing project route parameter.</p>
      </section>
    );
  }

  return (
    <section>
      <div className="app-row app-row-spaced">
        <div>
          <h2>Finance</h2>
          <p>Project: {projectId}</p>
        </div>
        <button type="button" onClick={() => void refresh()} disabled={loading}>
          Refresh
        </button>
      </div>

      {!canWrite ? <p className="app-state">Read-only mode: current role cannot mutate finance data.</p> : null}
      {loading ? <p className="app-state">Loading finance data…</p> : null}
      {errorMessage ? <p className="app-state app-error">{errorMessage}</p> : null}
      {successMessage ? <p className="app-state app-success">{successMessage}</p> : null}

      <div className="app-grid app-grid-2">
        <form className="app-form" onSubmit={onAddRate}>
          <h3>Performer rates</h3>
          <div className="app-grid app-grid-2">
            <label className="app-field">
              <span>Performer</span>
              <select
                value={rateDraft.performer_id}
                onChange={(event) => setRateDraft((previous) => ({ ...previous, performer_id: event.target.value }))}
                required
              >
                {performers.length === 0 ? <option value="">No performers</option> : null}
                {performers.map((performer) => (
                  <option key={performer.id} value={performer.id}>
                    {performer.display_name}
                  </option>
                ))}
              </select>
            </label>
            <label className="app-field">
              <span>Scope</span>
              <select
                value={rateDraft.project_id ?? ""}
                onChange={(event) =>
                  setRateDraft((previous) => ({
                    ...previous,
                    project_id: event.target.value || null,
                  }))
                }
              >
                <option value="">Business-unit default</option>
                <option value={projectId}>Current project</option>
              </select>
            </label>
            <label className="app-field">
              <span>Rate unit</span>
              <select
                value={rateDraft.rate_unit}
                onChange={(event) =>
                  setRateDraft((previous) => ({
                    ...previous,
                    rate_unit: event.target.value as RateUnit,
                  }))
                }
              >
                <option value="day">day</option>
                <option value="fte_month">fte_month</option>
              </select>
            </label>
            <label className="app-field">
              <span>Rate value</span>
              <input
                type="number"
                min={0}
                step="0.01"
                value={rateDraft.rate_value}
                onChange={(event) => setRateDraft((previous) => ({ ...previous, rate_value: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>Effective from</span>
              <input
                type="date"
                value={rateDraft.effective_from_month}
                onChange={(event) =>
                  setRateDraft((previous) => ({
                    ...previous,
                    effective_from_month: event.target.value,
                  }))
                }
                required
              />
            </label>
            <label className="app-field">
              <span>Effective to</span>
              <input
                type="date"
                value={rateDraft.effective_to_month}
                onChange={(event) =>
                  setRateDraft((previous) => ({
                    ...previous,
                    effective_to_month: event.target.value,
                  }))
                }
              />
            </label>
          </div>
          <div className="app-row">
            <button type="submit" disabled={!canWrite}>
              Upsert rate
            </button>
          </div>
          <table className="app-table">
            <thead>
              <tr>
                <th>Performer</th>
                <th>Scope</th>
                <th>Unit</th>
                <th>Value</th>
                <th>Range</th>
              </tr>
            </thead>
            <tbody>
              {rates.map((rate) => {
                const performerName = performers.find((item) => item.id === rate.performer_id)?.display_name ?? rate.performer_id;
                return (
                  <tr key={rate.id}>
                    <td>{performerName}</td>
                    <td>{rate.project_id ? "Project" : "BU default"}</td>
                    <td>{rate.rate_unit}</td>
                    <td>{money(rate.rate_value)}</td>
                    <td>
                      {rate.effective_from_month.slice(0, 10)} → {rate.effective_to_month?.slice(0, 10) ?? "open"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </form>

        <div className="app-form">
          <h3>Finance summary trend</h3>
          <p>
            Cumulative planned cost: <strong>{totals.cumulativePlannedCost}</strong>
          </p>
          <p>
            Cumulative actual cost: <strong>{totals.cumulativeActualCost}</strong>
          </p>
          <p>
            Cumulative revenue: <strong>{totals.cumulativeRevenue}</strong>
          </p>
          <table className="app-table">
            <thead>
              <tr>
                <th>Month</th>
                <th>Planned cost</th>
                <th>Actual cost</th>
                <th>Revenue</th>
                <th>Invoice</th>
              </tr>
            </thead>
            <tbody>
              {summaryMonths.map((month) => (
                <tr key={month.month_start}>
                  <td>{month.month_start.slice(0, 7)}</td>
                  <td>{money(month.planned_cost)}</td>
                  <td>{money(month.actual_cost)}</td>
                  <td>{money(month.revenue_amount)}</td>
                  <td>{money(month.invoice_amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="app-grid app-grid-3">
        <form className="app-form" onSubmit={onCreateRequest}>
          <h3>Financial requests</h3>
          <div className="app-grid app-grid-2">
            <label className="app-field">
              <span>No</span>
              <input
                value={requestDraft.request_no}
                onChange={(event) => setRequestDraft((previous) => ({ ...previous, request_no: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>Date</span>
              <input
                type="date"
                value={requestDraft.request_date}
                onChange={(event) => setRequestDraft((previous) => ({ ...previous, request_date: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>Month</span>
              <input
                type="date"
                value={requestDraft.month_start}
                onChange={(event) => setRequestDraft((previous) => ({ ...previous, month_start: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>Amount</span>
              <input
                type="number"
                min={0}
                step="0.01"
                value={requestDraft.amount}
                onChange={(event) => setRequestDraft((previous) => ({ ...previous, amount: event.target.value }))}
                required
              />
            </label>
          </div>
          <div className="app-row">
            <button type="submit" disabled={!canWrite}>
              Add request
            </button>
          </div>
          <ul className="app-list">
            {requests.map((request) => (
              <li key={request.id}>
                <span>
                  {request.request_no} — {money(request.amount)} {request.currency}
                </span>
              </li>
            ))}
          </ul>
        </form>

        <form className="app-form" onSubmit={onCreateInvoice}>
          <h3>Invoices</h3>
          <div className="app-grid app-grid-2">
            <label className="app-field">
              <span>No</span>
              <input
                value={invoiceDraft.invoice_no}
                onChange={(event) => setInvoiceDraft((previous) => ({ ...previous, invoice_no: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>Date</span>
              <input
                type="date"
                value={invoiceDraft.invoice_date}
                onChange={(event) => setInvoiceDraft((previous) => ({ ...previous, invoice_date: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>Month</span>
              <input
                type="date"
                value={invoiceDraft.month_start}
                onChange={(event) => setInvoiceDraft((previous) => ({ ...previous, month_start: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>Amount</span>
              <input
                type="number"
                min={0}
                step="0.01"
                value={invoiceDraft.amount}
                onChange={(event) => setInvoiceDraft((previous) => ({ ...previous, amount: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>Payment status</span>
              <input
                value={invoiceDraft.payment_status}
                onChange={(event) => setInvoiceDraft((previous) => ({ ...previous, payment_status: event.target.value }))}
              />
            </label>
            <label className="app-field">
              <span>Payment date</span>
              <input
                type="date"
                value={invoiceDraft.payment_date}
                onChange={(event) => setInvoiceDraft((previous) => ({ ...previous, payment_date: event.target.value }))}
              />
            </label>
          </div>
          <div className="app-row">
            <button type="submit" disabled={!canWrite}>
              Add invoice
            </button>
          </div>
          <ul className="app-list">
            {invoices.map((invoice) => (
              <li key={invoice.id}>
                <span>
                  {invoice.invoice_no} — {money(invoice.amount)} {invoice.currency}
                </span>
              </li>
            ))}
          </ul>
        </form>

        <form className="app-form" onSubmit={onCreateRevenue}>
          <h3>Revenues</h3>
          <div className="app-grid app-grid-2">
            <label className="app-field">
              <span>No</span>
              <input
                value={revenueDraft.revenue_no}
                onChange={(event) => setRevenueDraft((previous) => ({ ...previous, revenue_no: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>Date</span>
              <input
                type="date"
                value={revenueDraft.recognition_date}
                onChange={(event) =>
                  setRevenueDraft((previous) => ({
                    ...previous,
                    recognition_date: event.target.value,
                  }))
                }
                required
              />
            </label>
            <label className="app-field">
              <span>Month</span>
              <input
                type="date"
                value={revenueDraft.month_start}
                onChange={(event) => setRevenueDraft((previous) => ({ ...previous, month_start: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>Amount</span>
              <input
                type="number"
                min={0}
                step="0.01"
                value={revenueDraft.amount}
                onChange={(event) => setRevenueDraft((previous) => ({ ...previous, amount: event.target.value }))}
                required
              />
            </label>
          </div>
          <div className="app-row">
            <button type="submit" disabled={!canWrite}>
              Add revenue
            </button>
          </div>
          <ul className="app-list">
            {revenues.map((revenue) => (
              <li key={revenue.id}>
                <span>
                  {revenue.revenue_no} — {money(revenue.amount)} {revenue.currency}
                </span>
              </li>
            ))}
          </ul>
        </form>
      </div>
    </section>
  );
}

