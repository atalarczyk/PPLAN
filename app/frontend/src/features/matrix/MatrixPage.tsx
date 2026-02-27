import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { useAuth } from "../../app/auth/AuthProvider";
import { toErrorMessage } from "../shared/errors";
import { bulkUpsertMatrixEntries, getProjectMatrix, type MatrixPayload } from "./api";

interface EditableCell {
  planned: string;
  actual: string;
}

function entryKey(taskId: string, performerId: string, monthStart: string): string {
  return `${taskId}:${performerId}:${monthStart}`;
}

export function MatrixPage() {
  const { projectId } = useParams();
  const { hasPermission } = useAuth();

  const [matrix, setMatrix] = useState<MatrixPayload | null>(null);
  const [fromMonth, setFromMonth] = useState("");
  const [toMonth, setToMonth] = useState("");
  const [draftCells, setDraftCells] = useState<Record<string, EditableCell>>({});

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const canEdit = projectId ? hasPermission("matrix.edit", { projectId }) : false;

  const stagesById = useMemo(() => {
    return new Map((matrix?.stages ?? []).map((stage) => [stage.id, stage]));
  }, [matrix]);

  const tasksByStageId = useMemo(() => {
    const grouping = new Map<string, MatrixPayload["tasks"]>();
    for (const task of matrix?.tasks ?? []) {
      const bucket = grouping.get(task.stage_id) ?? [];
      bucket.push(task);
      grouping.set(task.stage_id, bucket);
    }
    return grouping;
  }, [matrix]);

  const performersById = useMemo(() => {
    return new Map((matrix?.performers ?? []).map((performer) => [performer.id, performer]));
  }, [matrix]);

  const originalEntriesMap = useMemo(() => {
    const map = new Map<string, EditableCell>();
    for (const row of matrix?.entries ?? []) {
      map.set(entryKey(row.task_id, row.performer_id, row.month_start), {
        planned: row.planned_person_days,
        actual: row.actual_person_days,
      });
    }
    return map;
  }, [matrix]);

  const stageTotalsByStageMonth = useMemo(() => {
    const totals = new Map<string, { planned: number; actual: number }>();
    if (!matrix) {
      return totals;
    }

    for (const task of matrix.tasks) {
      for (const monthTotal of task.monthly_totals) {
        const key = `${task.stage_id}:${monthTotal.month_start}`;
        const bucket = totals.get(key) ?? { planned: 0, actual: 0 };
        bucket.planned += Number(monthTotal.planned_person_days);
        bucket.actual += Number(monthTotal.actual_person_days);
        totals.set(key, bucket);
      }
    }

    return totals;
  }, [matrix]);

  useEffect(() => {
    let cancelled = false;

    async function loadInitial() {
      if (!projectId) {
        setErrorMessage("Missing project route parameter.");
        setLoading(false);
        return;
      }

      setLoading(true);
      setErrorMessage(null);
      try {
        const payload = await getProjectMatrix(projectId);
        if (cancelled) {
          return;
        }

        setMatrix(payload);
        const initialDraft: Record<string, EditableCell> = {};
        for (const row of payload.entries) {
          initialDraft[entryKey(row.task_id, row.performer_id, row.month_start)] = {
            planned: row.planned_person_days,
            actual: row.actual_person_days,
          };
        }
        setDraftCells(initialDraft);

        if (!fromMonth) {
          setFromMonth(payload.project.start_month.slice(0, 10));
        }
        if (!toMonth) {
          setToMonth(payload.project.end_month.slice(0, 10));
        }
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(toErrorMessage(error, "Unable to load matrix."));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void loadInitial();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  async function reloadWithCurrentFilter(): Promise<void> {
    if (!projectId) {
      return;
    }

    setLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const payload = await getProjectMatrix(projectId, {
        from_month: fromMonth || undefined,
        to_month: toMonth || undefined,
      });
      setMatrix(payload);

      const nextDraft: Record<string, EditableCell> = {};
      for (const row of payload.entries) {
        nextDraft[entryKey(row.task_id, row.performer_id, row.month_start)] = {
          planned: row.planned_person_days,
          actual: row.actual_person_days,
        };
      }
      setDraftCells(nextDraft);
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to refresh matrix."));
    } finally {
      setLoading(false);
    }
  }

  function onCellChange(taskId: string, performerId: string, monthStart: string, mode: "planned" | "actual", value: string) {
    const key = entryKey(taskId, performerId, monthStart);
    setDraftCells((previous) => {
      const current = previous[key] ?? originalEntriesMap.get(key) ?? { planned: "0", actual: "0" };
      return {
        ...previous,
        [key]: {
          ...current,
          [mode]: value,
        },
      };
    });
  }

  const changedEntries = useMemo(() => {
    const updates: Array<{ task_id: string; performer_id: string; month_start: string; planned_person_days: string; actual_person_days: string }> = [];

    for (const row of matrix?.entries ?? []) {
      const key = entryKey(row.task_id, row.performer_id, row.month_start);
      const original = originalEntriesMap.get(key) ?? { planned: "0", actual: "0" };
      const draft = draftCells[key] ?? original;
      if (draft.planned !== original.planned || draft.actual !== original.actual) {
        updates.push({
          task_id: row.task_id,
          performer_id: row.performer_id,
          month_start: row.month_start,
          planned_person_days: draft.planned,
          actual_person_days: draft.actual,
        });
      }
    }

    return updates;
  }, [matrix, draftCells, originalEntriesMap]);

  async function onSaveChanges() {
    if (!projectId || !canEdit || changedEntries.length === 0) {
      return;
    }

    setSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const saveResult = await bulkUpsertMatrixEntries(projectId, changedEntries);
      setSuccessMessage(`Saved ${saveResult.updated_entries} matrix entries.`);
      await reloadWithCurrentFilter();
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to save matrix updates."));
    } finally {
      setSaving(false);
    }
  }

  if (!projectId) {
    return (
      <section>
        <h2>Matrix Editor</h2>
        <p className="app-state app-error">Missing project route parameter.</p>
      </section>
    );
  }

  return (
    <section>
      <div className="app-row app-row-spaced">
        <div>
          <h2>Matrix Editor</h2>
          <p>
            Project: <strong>{matrix?.project.code ?? projectId}</strong>
          </p>
        </div>
        <div className="app-row app-row-wrap">
          <button type="button" className="app-button-secondary" onClick={() => void reloadWithCurrentFilter()} disabled={loading || saving}>
            Refresh
          </button>
          <button type="button" onClick={() => void onSaveChanges()} disabled={!canEdit || saving || changedEntries.length === 0}>
            Save changes ({changedEntries.length})
          </button>
        </div>
      </div>

      <div className="app-row app-row-wrap">
        <label className="app-field">
          <span>From month</span>
          <input type="date" value={fromMonth} onChange={(event) => setFromMonth(event.target.value)} />
        </label>
        <label className="app-field">
          <span>To month</span>
          <input type="date" value={toMonth} onChange={(event) => setToMonth(event.target.value)} />
        </label>
        <button type="button" className="app-button-secondary" onClick={() => void reloadWithCurrentFilter()} disabled={loading || saving}>
          Apply range
        </button>
      </div>

      {!canEdit ? <p className="app-state">Read-only mode: current role cannot write matrix values.</p> : null}
      {loading ? <p className="app-state">Loading matrix…</p> : null}
      {errorMessage ? <p className="app-state app-error">{errorMessage}</p> : null}
      {successMessage ? <p className="app-state app-success">{successMessage}</p> : null}

      {!loading && matrix && matrix.months.length === 0 ? <p className="app-state">No month columns in selected range.</p> : null}

      {!loading && matrix && matrix.months.length > 0 ? (
        <div className="app-table-scroll">
          <table className="app-table app-table-matrix">
            <thead>
              <tr>
                <th>Hierarchy</th>
                {matrix.months.map((monthStart) => (
                  <th key={monthStart}>{monthStart.slice(0, 7)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {matrix.stages
                .slice()
                .sort((left, right) => left.sequence_no - right.sequence_no)
                .map((stage) => {
                  const stageTasks = (tasksByStageId.get(stage.id) ?? []).slice().sort((left, right) => left.sequence_no - right.sequence_no);

                  return (
                    <>
                      <tr key={`stage-${stage.id}`} className="matrix-row-stage">
                        <td>
                          <span className="matrix-stage-label">{stage.name}</span>
                          <span className={`matrix-color-token matrix-color-${stage.color_token}`}>{stage.color_token}</span>
                        </td>
                        {matrix.months.map((monthStart) => {
                          const bucket = stageTotalsByStageMonth.get(`${stage.id}:${monthStart}`) ?? { planned: 0, actual: 0 };
                          return (
                            <td key={`stage-${stage.id}-${monthStart}`}>
                              <span className="matrix-readonly-value">
                                {bucket.planned.toFixed(2)} / {bucket.actual.toFixed(2)}
                              </span>
                            </td>
                          );
                        })}
                      </tr>

                      {stageTasks.map((task) => (
                        <>
                          <tr key={`task-${task.id}`} className="matrix-row-task">
                            <td>
                              <span className="matrix-task-label">
                                {task.code} — {task.name}
                              </span>
                            </td>
                            {matrix.months.map((monthStart) => {
                              const total = task.monthly_totals.find((item) => item.month_start === monthStart);
                              return (
                                <td key={`task-${task.id}-${monthStart}`}>
                                  <span className="matrix-readonly-value">
                                    {(Number(total?.planned_person_days ?? "0") || 0).toFixed(2)} /{" "}
                                    {(Number(total?.actual_person_days ?? "0") || 0).toFixed(2)}
                                  </span>
                                </td>
                              );
                            })}
                          </tr>

                          {task.performer_ids.map((performerId) => {
                            const performer = performersById.get(performerId);
                            return (
                              <tr key={`performer-${task.id}-${performerId}`} className="matrix-row-performer">
                                <td>
                                  <span className="matrix-performer-label">↳ {performer?.display_name ?? performerId}</span>
                                </td>
                                {matrix.months.map((monthStart) => {
                                  const key = entryKey(task.id, performerId, monthStart);
                                  const current = draftCells[key] ?? originalEntriesMap.get(key) ?? { planned: "0", actual: "0" };

                                  return (
                                    <td key={`performer-${task.id}-${performerId}-${monthStart}`}>
                                      <div className="matrix-edit-pair">
                                        <input
                                          type="number"
                                          min={0}
                                          step="0.01"
                                          value={current.planned}
                                          onChange={(event) =>
                                            onCellChange(task.id, performerId, monthStart, "planned", event.target.value)
                                          }
                                          disabled={!canEdit || saving}
                                          aria-label={`Planned for ${performer?.display_name ?? performerId} ${monthStart}`}
                                        />
                                        <input
                                          type="number"
                                          min={0}
                                          step="0.01"
                                          value={current.actual}
                                          onChange={(event) =>
                                            onCellChange(task.id, performerId, monthStart, "actual", event.target.value)
                                          }
                                          disabled={!canEdit || saving}
                                          aria-label={`Actual for ${performer?.display_name ?? performerId} ${monthStart}`}
                                        />
                                      </div>
                                    </td>
                                  );
                                })}
                              </tr>
                            );
                          })}
                        </>
                      ))}
                    </>
                  );
                })}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

