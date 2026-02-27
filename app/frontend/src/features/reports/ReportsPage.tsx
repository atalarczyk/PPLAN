import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { useAuth } from "../../app/auth/AuthProvider";
import { listProjectPerformers, listProjectTasks, type PerformerRecord, type TaskRecord } from "../projects/api";
import { toErrorMessage } from "../shared/errors";
import { exportReport } from "../exports/api";
import { getProjectReport, type ReportKey, type ReportPayload } from "./api";

interface ReportFilterState {
  reportKey: ReportKey;
  fromMonth: string;
  toMonth: string;
  performerIds: string[];
  taskIds: string[];
}

const DEFAULT_FILTERS: ReportFilterState = {
  reportKey: "effort-by-performer",
  fromMonth: "",
  toMonth: "",
  performerIds: [],
  taskIds: [],
};

function getRowLabel(row: ReportPayload["rows"][number]): string {
  if (row.performer_name) {
    return row.performer_name;
  }
  if (row.task_name) {
    return row.stage_name ? `${row.task_name} (${row.stage_name})` : row.task_name;
  }
  return "—";
}

export function ReportsPage() {
  const { projectId } = useParams();
  const { hasPermission } = useAuth();

  const [performers, setPerformers] = useState<PerformerRecord[]>([]);
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [filters, setFilters] = useState<ReportFilterState>(DEFAULT_FILTERS);
  const [report, setReport] = useState<ReportPayload | null>(null);

  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const canExport = projectId ? hasPermission("reports.export", { projectId }) : false;

  const monthHeaders = useMemo(() => report?.months ?? [], [report]);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      if (!projectId) {
        setLoading(false);
        setErrorMessage("Missing project route parameter.");
        return;
      }

      setLoading(true);
      setErrorMessage(null);
      try {
        const [performerRows, taskRows, reportPayload] = await Promise.all([
          listProjectPerformers(projectId),
          listProjectTasks(projectId),
          getProjectReport(projectId, DEFAULT_FILTERS.reportKey),
        ]);

        if (cancelled) {
          return;
        }

        setPerformers(performerRows);
        setTasks(taskRows);
        setReport(reportPayload);
        setFilters((previous) => ({
          ...previous,
          fromMonth: reportPayload.from_month,
          toMonth: reportPayload.to_month,
        }));
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(toErrorMessage(error, "Unable to load reports."));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  async function runReport() {
    if (!projectId) {
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const payload = await getProjectReport(projectId, filters.reportKey, {
        from_month: filters.fromMonth || undefined,
        to_month: filters.toMonth || undefined,
        performer_id: filters.performerIds.length > 0 ? filters.performerIds : undefined,
        task_id: filters.taskIds.length > 0 ? filters.taskIds : undefined,
      });
      setReport(payload);
      setSuccessMessage(`Loaded report ${payload.report_key}.`);
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to run report."));
    } finally {
      setLoading(false);
    }
  }

  async function onExport(format: "csv" | "xlsx") {
    if (!projectId || !report || !canExport) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const file = await exportReport({
        reportKey: report.report_key,
        format,
        projectId,
        fromMonth: filters.fromMonth || undefined,
        toMonth: filters.toMonth || undefined,
        performerIds: filters.performerIds.length > 0 ? filters.performerIds : undefined,
        taskIds: filters.taskIds.length > 0 ? filters.taskIds : undefined,
      });

      const downloadUrl = URL.createObjectURL(file.content);
      const anchor = document.createElement("a");
      anchor.href = downloadUrl;
      anchor.download = file.filename;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(downloadUrl);

      setSuccessMessage(`Exported ${file.filename}.`);
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to export report."));
    }
  }

  function toggleValue(current: string[], value: string): string[] {
    return current.includes(value) ? current.filter((item) => item !== value) : [...current, value];
  }

  if (!projectId) {
    return (
      <section>
        <h2>Reports</h2>
        <p className="app-state app-error">Missing project route parameter.</p>
      </section>
    );
  }

  return (
    <section>
      <div className="app-row app-row-spaced">
        <div>
          <h2>Reports</h2>
          <p>Project: {projectId}</p>
        </div>
        <div className="app-row app-row-wrap">
          <button type="button" className="app-button-secondary" onClick={() => void runReport()} disabled={loading}>
            Run report
          </button>
          <button type="button" onClick={() => void onExport("csv")} disabled={!report || !canExport}>
            Export CSV
          </button>
          <button type="button" onClick={() => void onExport("xlsx")} disabled={!report || !canExport}>
            Export XLSX
          </button>
        </div>
      </div>

      {!canExport ? <p className="app-state">Export unavailable for current permission scope.</p> : null}
      {loading ? <p className="app-state">Loading report data…</p> : null}
      {errorMessage ? <p className="app-state app-error">{errorMessage}</p> : null}
      {successMessage ? <p className="app-state app-success">{successMessage}</p> : null}

      <div className="app-form">
        <h3>Filters</h3>
        <div className="app-grid app-grid-3">
          <label className="app-field">
            <span>Report type</span>
            <select
              value={filters.reportKey}
              onChange={(event) =>
                setFilters((previous) => ({
                  ...previous,
                  reportKey: event.target.value as ReportKey,
                }))
              }
            >
              <option value="effort-by-performer">Effort by performer</option>
              <option value="effort-by-task">Effort by task</option>
              <option value="cost-by-performer">Cost by performer</option>
              <option value="cost-by-task">Cost by task</option>
            </select>
          </label>
          <label className="app-field">
            <span>From month</span>
            <input
              type="date"
              value={filters.fromMonth}
              onChange={(event) => setFilters((previous) => ({ ...previous, fromMonth: event.target.value }))}
            />
          </label>
          <label className="app-field">
            <span>To month</span>
            <input
              type="date"
              value={filters.toMonth}
              onChange={(event) => setFilters((previous) => ({ ...previous, toMonth: event.target.value }))}
            />
          </label>
        </div>

        <div className="app-grid app-grid-2">
          <fieldset className="app-fieldset">
            <legend>Performers</legend>
            <div className="app-checkbox-list">
              {performers.map((performer) => (
                <label key={performer.id}>
                  <input
                    type="checkbox"
                    checked={filters.performerIds.includes(performer.id)}
                    onChange={() =>
                      setFilters((previous) => ({
                        ...previous,
                        performerIds: toggleValue(previous.performerIds, performer.id),
                      }))
                    }
                  />
                  {performer.display_name}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset className="app-fieldset">
            <legend>Tasks</legend>
            <div className="app-checkbox-list">
              {tasks.map((task) => (
                <label key={task.id}>
                  <input
                    type="checkbox"
                    checked={filters.taskIds.includes(task.id)}
                    onChange={() =>
                      setFilters((previous) => ({
                        ...previous,
                        taskIds: toggleValue(previous.taskIds, task.id),
                      }))
                    }
                  />
                  {task.code} — {task.name}
                </label>
              ))}
            </div>
          </fieldset>
        </div>
      </div>

      {report ? (
        <div className="app-table-scroll">
          <table className="app-table">
            <thead>
              <tr>
                <th>Row</th>
                {monthHeaders.map((month) => (
                  <th key={`month-${month}`}>{month.slice(0, 7)}</th>
                ))}
                <th>Total variance</th>
              </tr>
            </thead>
            <tbody>
              {report.rows.length === 0 ? (
                <tr>
                  <td colSpan={monthHeaders.length + 2}>No rows returned for current filters.</td>
                </tr>
              ) : (
                report.rows.map((row, index) => (
                  <tr key={`report-row-${index}`}>
                    <td>{getRowLabel(row)}</td>
                    {row.months.map((month) => (
                      <td key={`${getRowLabel(row)}-${month.month_start}`}>
                        {month.planned_cost ?? month.planned ?? "0"} / {month.actual_cost ?? month.actual ?? "0"}
                      </td>
                    ))}
                    <td>{row.totals.variance}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

