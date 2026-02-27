import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { toErrorMessage } from "../shared/errors";
import { getProjectDashboard, type ProjectDashboardPayload } from "./api";

function num(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function DashboardPage() {
  const { projectId } = useParams();
  const [data, setData] = useState<ProjectDashboardPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const latest = useMemo(() => {
    if (!data || data.cumulative_cost_trend.length === 0 || data.realization_trend.length === 0) {
      return null;
    }

    const cost = data.cumulative_cost_trend[data.cumulative_cost_trend.length - 1];
    const realization = data.realization_trend[data.realization_trend.length - 1];

    return {
      cumulativePlannedCost: num(cost.cumulative_planned_cost).toFixed(2),
      cumulativeActualCost: num(cost.cumulative_actual_cost).toFixed(2),
      cumulativeRevenue: num(realization.cumulative_revenue).toFixed(2),
      realizationPercent: num(realization.realization_percent).toFixed(2),
      cumulativeMargin: num(realization.cumulative_margin).toFixed(2),
    };
  }, [data]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!projectId) {
        setLoading(false);
        setErrorMessage("Missing project route parameter.");
        return;
      }

      setLoading(true);
      setErrorMessage(null);
      try {
        const payload = await getProjectDashboard(projectId);
        if (!cancelled) {
          setData(payload);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(toErrorMessage(error, "Unable to load project dashboard."));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  async function refresh() {
    if (!projectId) {
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      const payload = await getProjectDashboard(projectId);
      setData(payload);
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to refresh project dashboard."));
    } finally {
      setLoading(false);
    }
  }

  if (!projectId) {
    return (
      <section>
        <h2>Project Dashboard</h2>
        <p className="app-state app-error">Missing project route parameter.</p>
      </section>
    );
  }

  return (
    <section>
      <div className="app-row app-row-spaced">
        <div>
          <h2>Project Dashboard</h2>
          <p>Project: {projectId}</p>
        </div>
        <button type="button" onClick={() => void refresh()} disabled={loading}>
          Refresh
        </button>
      </div>

      {loading ? <p className="app-state">Loading dashboard…</p> : null}
      {errorMessage ? <p className="app-state app-error">{errorMessage}</p> : null}

      {data && latest ? (
        <>
          <div className="app-grid app-grid-5">
            <div className="app-kpi-card">
              <span>Cumulative planned cost</span>
              <strong>{latest.cumulativePlannedCost}</strong>
            </div>
            <div className="app-kpi-card">
              <span>Cumulative actual cost</span>
              <strong>{latest.cumulativeActualCost}</strong>
            </div>
            <div className="app-kpi-card">
              <span>Cumulative revenue</span>
              <strong>{latest.cumulativeRevenue}</strong>
            </div>
            <div className="app-kpi-card">
              <span>Cumulative margin</span>
              <strong>{latest.cumulativeMargin}</strong>
            </div>
            <div className="app-kpi-card">
              <span>Realization %</span>
              <strong>{latest.realizationPercent}%</strong>
            </div>
          </div>

          <div className="app-grid app-grid-2">
            <div className="app-form">
              <h3>Cumulative planned vs actual trend</h3>
              <table className="app-table">
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>Planned cost</th>
                    <th>Actual cost</th>
                    <th>Cumulative planned</th>
                    <th>Cumulative actual</th>
                  </tr>
                </thead>
                <tbody>
                  {data.cumulative_cost_trend.map((point) => (
                    <tr key={point.month_start}>
                      <td>{point.month_start.slice(0, 7)}</td>
                      <td>{num(point.planned_cost).toFixed(2)}</td>
                      <td>{num(point.actual_cost).toFixed(2)}</td>
                      <td>{num(point.cumulative_planned_cost).toFixed(2)}</td>
                      <td>{num(point.cumulative_actual_cost).toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="app-form">
              <h3>Realization trend</h3>
              <table className="app-table">
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>Cumulative revenue</th>
                    <th>Cumulative actual</th>
                    <th>Margin</th>
                    <th>Realization %</th>
                  </tr>
                </thead>
                <tbody>
                  {data.realization_trend.map((point) => (
                    <tr key={point.month_start}>
                      <td>{point.month_start.slice(0, 7)}</td>
                      <td>{num(point.cumulative_revenue).toFixed(2)}</td>
                      <td>{num(point.cumulative_actual_cost).toFixed(2)}</td>
                      <td>{num(point.cumulative_margin).toFixed(2)}</td>
                      <td>{num(point.realization_percent).toFixed(2)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="app-form">
            <h3>Workload trend by performer</h3>
            <table className="app-table">
              <thead>
                <tr>
                  <th>Performer</th>
                  {data.cumulative_cost_trend.map((point) => (
                    <th key={`wl-header-${point.month_start}`}>{point.month_start.slice(0, 7)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.workload_trend.length === 0 ? (
                  <tr>
                    <td colSpan={data.cumulative_cost_trend.length + 1}>No workload data.</td>
                  </tr>
                ) : (
                  data.workload_trend.map((performer) => (
                    <tr key={performer.performer_id}>
                      <td>{performer.performer_name}</td>
                      {performer.months.map((month) => (
                        <td key={`${performer.performer_id}-${month.month_start}`}>
                          {num(month.planned_person_days).toFixed(2)} / {num(month.actual_person_days).toFixed(2)}
                        </td>
                      ))}
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </section>
  );
}

