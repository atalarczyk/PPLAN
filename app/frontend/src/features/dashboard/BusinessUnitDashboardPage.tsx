import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { toErrorMessage } from "../shared/errors";
import { getBusinessUnitDashboard, type BusinessUnitDashboardPayload } from "./api";

function num(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function BusinessUnitDashboardPage() {
  const { businessUnitId } = useParams();
  const [data, setData] = useState<BusinessUnitDashboardPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const latest = useMemo(() => {
    if (!data || data.aggregated_cumulative_cost_trend.length === 0 || data.realization_trend.length === 0) {
      return null;
    }

    const cost = data.aggregated_cumulative_cost_trend[data.aggregated_cumulative_cost_trend.length - 1];
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
      if (!businessUnitId) {
        setLoading(false);
        setErrorMessage("Missing business-unit route parameter.");
        return;
      }

      setLoading(true);
      setErrorMessage(null);
      try {
        const payload = await getBusinessUnitDashboard(businessUnitId);
        if (!cancelled) {
          setData(payload);
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(toErrorMessage(error, "Unable to load business-unit dashboard."));
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
  }, [businessUnitId]);

  async function refresh() {
    if (!businessUnitId) {
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    try {
      const payload = await getBusinessUnitDashboard(businessUnitId);
      setData(payload);
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to refresh business-unit dashboard."));
    } finally {
      setLoading(false);
    }
  }

  if (!businessUnitId) {
    return (
      <section>
        <h2>Business Unit Dashboard</h2>
        <p className="app-state app-error">Missing business-unit route parameter.</p>
      </section>
    );
  }

  return (
    <section>
      <div className="app-row app-row-spaced">
        <div>
          <h2>Business Unit Dashboard</h2>
          <p>Business unit: {businessUnitId}</p>
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
              <span>BU cumulative planned cost</span>
              <strong>{latest.cumulativePlannedCost}</strong>
            </div>
            <div className="app-kpi-card">
              <span>BU cumulative actual cost</span>
              <strong>{latest.cumulativeActualCost}</strong>
            </div>
            <div className="app-kpi-card">
              <span>BU cumulative revenue</span>
              <strong>{latest.cumulativeRevenue}</strong>
            </div>
            <div className="app-kpi-card">
              <span>BU cumulative margin</span>
              <strong>{latest.cumulativeMargin}</strong>
            </div>
            <div className="app-kpi-card">
              <span>BU realization %</span>
              <strong>{latest.realizationPercent}%</strong>
            </div>
          </div>

          <div className="app-grid app-grid-2">
            <div className="app-form">
              <h3>Aggregated cumulative planned vs actual trend</h3>
              <table className="app-table">
                <thead>
                  <tr>
                    <th>Month</th>
                    <th>Planned</th>
                    <th>Actual</th>
                    <th>Cumulative planned</th>
                    <th>Cumulative actual</th>
                  </tr>
                </thead>
                <tbody>
                  {data.aggregated_cumulative_cost_trend.map((point) => (
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
            <h3>Workload heatmap (performer/month)</h3>
            <table className="app-table">
              <thead>
                <tr>
                  <th>Performer</th>
                  {data.aggregated_cumulative_cost_trend.map((point) => (
                    <th key={`wl-header-${point.month_start}`}>{point.month_start.slice(0, 7)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.workload_heatmap.length === 0 ? (
                  <tr>
                    <td colSpan={data.aggregated_cumulative_cost_trend.length + 1}>No workload data.</td>
                  </tr>
                ) : (
                  data.workload_heatmap.map((performer) => (
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
