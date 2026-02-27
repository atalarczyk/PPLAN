import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";

import { toErrorMessage } from "../shared/errors";
import {
  createProjectPerformer,
  createProjectStage,
  createProjectTask,
  createTaskPerformerAssignment,
  deleteProjectPerformer,
  deleteProjectStage,
  deleteProjectTask,
  deleteTaskPerformerAssignment,
  getProject,
  listProjectPerformers,
  listProjectStages,
  listProjectTasks,
  listTaskPerformerAssignments,
  updateProjectPerformer,
  updateProjectTask,
  type PerformerRecord,
  type ProjectRecord,
  type StageRecord,
  type TaskPerformerAssignmentRecord,
  type TaskRecord,
} from "./api";

interface StageDraft {
  name: string;
  start_month: string;
  end_month: string;
  color_token: string;
  sequence_no: number;
}

interface TaskDraft {
  stage_id: string;
  code: string;
  name: string;
  sequence_no: number;
  active: boolean;
}

interface PerformerDraft {
  display_name: string;
  external_ref: string;
  active: boolean;
}

interface AssignmentDraft {
  task_id: string;
  performer_id: string;
}

const DEFAULT_STAGE_DRAFT: StageDraft = {
  name: "",
  start_month: "",
  end_month: "",
  color_token: "blue",
  sequence_no: 1,
};

const DEFAULT_TASK_DRAFT: TaskDraft = {
  stage_id: "",
  code: "",
  name: "",
  sequence_no: 1,
  active: true,
};

const DEFAULT_PERFORMER_DRAFT: PerformerDraft = {
  display_name: "",
  external_ref: "",
  active: true,
};

const DEFAULT_ASSIGNMENT_DRAFT: AssignmentDraft = {
  task_id: "",
  performer_id: "",
};

export function ProjectSettingsPage() {
  const { projectId } = useParams();

  const [project, setProject] = useState<ProjectRecord | null>(null);
  const [stages, setStages] = useState<StageRecord[]>([]);
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [performers, setPerformers] = useState<PerformerRecord[]>([]);
  const [assignments, setAssignments] = useState<TaskPerformerAssignmentRecord[]>([]);

  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [stageDraft, setStageDraft] = useState<StageDraft>(DEFAULT_STAGE_DRAFT);
  const [taskDraft, setTaskDraft] = useState<TaskDraft>(DEFAULT_TASK_DRAFT);
  const [performerDraft, setPerformerDraft] = useState<PerformerDraft>(DEFAULT_PERFORMER_DRAFT);
  const [assignmentDraft, setAssignmentDraft] = useState<AssignmentDraft>(DEFAULT_ASSIGNMENT_DRAFT);

  const stageById = useMemo(() => new Map(stages.map((stage) => [stage.id, stage])), [stages]);
  const taskById = useMemo(() => new Map(tasks.map((task) => [task.id, task])), [tasks]);
  const performerById = useMemo(() => new Map(performers.map((performer) => [performer.id, performer])), [performers]);

  const assignmentKeySet = useMemo(
    () => new Set(assignments.map((assignment) => `${assignment.task_id}:${assignment.performer_id}`)),
    [assignments],
  );

  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      if (!projectId) {
        setErrorMessage("Missing project context in route.");
        setLoading(false);
        return;
      }

      setLoading(true);
      setErrorMessage(null);
      try {
        const [projectPayload, stageRows, taskRows, performerRows, assignmentRows] = await Promise.all([
          getProject(projectId),
          listProjectStages(projectId),
          listProjectTasks(projectId),
          listProjectPerformers(projectId),
          listTaskPerformerAssignments(projectId),
        ]);

        if (cancelled) {
          return;
        }

        setProject(projectPayload);
        setStages(stageRows);
        setTasks(taskRows);
        setPerformers(performerRows);
        setAssignments(assignmentRows);

        setStageDraft((previous) => ({
          ...previous,
          start_month: previous.start_month || projectPayload.start_month.slice(0, 10),
          end_month: previous.end_month || projectPayload.end_month.slice(0, 10),
          sequence_no: stageRows.length + 1,
        }));
        setTaskDraft((previous) => ({
          ...previous,
          stage_id: previous.stage_id || stageRows[0]?.id || "",
          sequence_no: taskRows.length + 1,
        }));
        setAssignmentDraft((previous) => ({
          task_id: previous.task_id || taskRows[0]?.id || "",
          performer_id: previous.performer_id || performerRows[0]?.id || "",
        }));
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(toErrorMessage(error, "Unable to load project settings."));
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
      const [stageRows, taskRows, performerRows, assignmentRows] = await Promise.all([
        listProjectStages(projectId),
        listProjectTasks(projectId),
        listProjectPerformers(projectId),
        listTaskPerformerAssignments(projectId),
      ]);
      setStages(stageRows);
      setTasks(taskRows);
      setPerformers(performerRows);
      setAssignments(assignmentRows);
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to refresh project settings."));
    } finally {
      setLoading(false);
    }
  }

  async function onCreateStage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await createProjectStage(projectId, {
        ...stageDraft,
        name: stageDraft.name.trim(),
      });
      setStageDraft((previous) => ({
        ...DEFAULT_STAGE_DRAFT,
        start_month: previous.start_month,
        end_month: previous.end_month,
        sequence_no: previous.sequence_no + 1,
      }));
      await refresh();
      setSuccessMessage("Stage created.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to create stage."));
    }
  }

  async function onCreateTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await createProjectTask(projectId, {
        ...taskDraft,
        code: taskDraft.code.trim(),
        name: taskDraft.name.trim(),
      });
      setTaskDraft((previous) => ({
        ...DEFAULT_TASK_DRAFT,
        stage_id: previous.stage_id,
        sequence_no: previous.sequence_no + 1,
      }));
      await refresh();
      setSuccessMessage("Task created.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to create task."));
    }
  }

  async function onCreatePerformer(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await createProjectPerformer(projectId, {
        display_name: performerDraft.display_name.trim(),
        external_ref: performerDraft.external_ref.trim() || null,
        active: performerDraft.active,
      });
      setPerformerDraft(DEFAULT_PERFORMER_DRAFT);
      await refresh();
      setSuccessMessage("Performer created.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to create performer."));
    }
  }

  async function onCreateAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await createTaskPerformerAssignment(projectId, assignmentDraft);
      await refresh();
      setSuccessMessage("Assignment created.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to create assignment."));
    }
  }

  async function onDeleteStage(stageId: string) {
    if (!projectId) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await deleteProjectStage(projectId, stageId);
      await refresh();
      setSuccessMessage("Stage deleted.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to delete stage."));
    }
  }

  async function onDeleteTask(taskId: string) {
    if (!projectId) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await deleteProjectTask(projectId, taskId);
      await refresh();
      setSuccessMessage("Task deleted.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to delete task."));
    }
  }

  async function onDeletePerformer(performerId: string) {
    if (!projectId) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await deleteProjectPerformer(projectId, performerId);
      await refresh();
      setSuccessMessage("Performer deleted.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to delete performer."));
    }
  }

  async function onDeleteAssignment(taskId: string, performerId: string) {
    if (!projectId) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await deleteTaskPerformerAssignment(projectId, taskId, performerId);
      await refresh();
      setSuccessMessage("Assignment deleted.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to delete assignment."));
    }
  }

  async function onToggleTaskActive(task: TaskRecord) {
    if (!projectId) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await updateProjectTask(projectId, task.id, { active: !task.active });
      await refresh();
      setSuccessMessage(`Task ${task.code} updated.`);
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to update task."));
    }
  }

  async function onTogglePerformerActive(performer: PerformerRecord) {
    if (!projectId) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await updateProjectPerformer(projectId, performer.id, {
        active: !performer.active,
      });
      await refresh();
      setSuccessMessage(`Performer ${performer.display_name} updated.`);
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to update performer."));
    }
  }

  if (!projectId) {
    return (
      <section>
        <h2>Project Settings</h2>
        <p className="app-state app-error">Missing project route parameter.</p>
      </section>
    );
  }

  return (
    <section>
      <div className="app-row app-row-spaced">
        <div>
          <h2>Project Settings</h2>
          <p>
            Project: <strong>{project?.code ?? projectId}</strong>
          </p>
        </div>
        <button type="button" onClick={() => void refresh()} disabled={loading}>
          Refresh
        </button>
      </div>

      {loading ? <p className="app-state">Loading settings…</p> : null}
      {errorMessage ? <p className="app-state app-error">{errorMessage}</p> : null}
      {successMessage ? <p className="app-state app-success">{successMessage}</p> : null}

      <div className="app-grid app-grid-2">
        <form className="app-form" onSubmit={onCreateStage}>
          <h3>Stages</h3>
          <div className="app-grid app-grid-2">
            <label className="app-field">
              <span>Name</span>
              <input
                value={stageDraft.name}
                onChange={(event) => setStageDraft((previous) => ({ ...previous, name: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>Color token</span>
              <input
                value={stageDraft.color_token}
                onChange={(event) => setStageDraft((previous) => ({ ...previous, color_token: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>Start month</span>
              <input
                type="date"
                value={stageDraft.start_month}
                onChange={(event) => setStageDraft((previous) => ({ ...previous, start_month: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>End month</span>
              <input
                type="date"
                value={stageDraft.end_month}
                onChange={(event) => setStageDraft((previous) => ({ ...previous, end_month: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>Sequence</span>
              <input
                type="number"
                min={0}
                value={stageDraft.sequence_no}
                onChange={(event) =>
                  setStageDraft((previous) => ({
                    ...previous,
                    sequence_no: Number(event.target.value),
                  }))
                }
                required
              />
            </label>
          </div>
          <div className="app-row">
            <button type="submit">Add stage</button>
          </div>
          <ul className="app-list">
            {stages.map((stage) => (
              <li key={stage.id}>
                <span>
                  {stage.sequence_no}. {stage.name} ({stage.start_month.slice(0, 7)} → {stage.end_month.slice(0, 7)})
                </span>
                <button type="button" className="app-button-danger" onClick={() => void onDeleteStage(stage.id)}>
                  Delete
                </button>
              </li>
            ))}
          </ul>
        </form>

        <form className="app-form" onSubmit={onCreateTask}>
          <h3>Tasks</h3>
          <div className="app-grid app-grid-2">
            <label className="app-field">
              <span>Stage</span>
              <select
                value={taskDraft.stage_id}
                onChange={(event) => setTaskDraft((previous) => ({ ...previous, stage_id: event.target.value }))}
                required
              >
                {stages.length === 0 ? <option value="">No stages</option> : null}
                {stages.map((stage) => (
                  <option key={stage.id} value={stage.id}>
                    {stage.sequence_no}. {stage.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="app-field">
              <span>Code</span>
              <input
                value={taskDraft.code}
                onChange={(event) => setTaskDraft((previous) => ({ ...previous, code: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>Name</span>
              <input
                value={taskDraft.name}
                onChange={(event) => setTaskDraft((previous) => ({ ...previous, name: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>Sequence</span>
              <input
                type="number"
                min={0}
                value={taskDraft.sequence_no}
                onChange={(event) =>
                  setTaskDraft((previous) => ({
                    ...previous,
                    sequence_no: Number(event.target.value),
                  }))
                }
                required
              />
            </label>
          </div>
          <div className="app-row">
            <button type="submit" disabled={stages.length === 0}>
              Add task
            </button>
          </div>
          <table className="app-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Stage</th>
                <th>Active</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.id}>
                  <td>{task.code}</td>
                  <td>{task.name}</td>
                  <td>{stageById.get(task.stage_id)?.name ?? task.stage_id}</td>
                  <td>
                    <button type="button" className="app-button-secondary" onClick={() => void onToggleTaskActive(task)}>
                      {task.active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                  <td>
                    <button type="button" className="app-button-danger" onClick={() => void onDeleteTask(task.id)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </form>
      </div>

      <div className="app-grid app-grid-2">
        <form className="app-form" onSubmit={onCreatePerformer}>
          <h3>Performers</h3>
          <div className="app-grid app-grid-2">
            <label className="app-field">
              <span>Display name</span>
              <input
                value={performerDraft.display_name}
                onChange={(event) =>
                  setPerformerDraft((previous) => ({
                    ...previous,
                    display_name: event.target.value,
                  }))
                }
                required
              />
            </label>
            <label className="app-field">
              <span>External reference</span>
              <input
                value={performerDraft.external_ref}
                onChange={(event) =>
                  setPerformerDraft((previous) => ({
                    ...previous,
                    external_ref: event.target.value,
                  }))
                }
              />
            </label>
          </div>
          <div className="app-row">
            <button type="submit">Add performer</button>
          </div>
          <table className="app-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>External ref</th>
                <th>Active</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {performers.map((performer) => (
                <tr key={performer.id}>
                  <td>{performer.display_name}</td>
                  <td>{performer.external_ref ?? "—"}</td>
                  <td>
                    <button
                      type="button"
                      className="app-button-secondary"
                      onClick={() => void onTogglePerformerActive(performer)}
                    >
                      {performer.active ? "Deactivate" : "Activate"}
                    </button>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="app-button-danger"
                      onClick={() => void onDeletePerformer(performer.id)}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </form>

        <form className="app-form" onSubmit={onCreateAssignment}>
          <h3>Task-performer assignments</h3>
          <div className="app-grid app-grid-2">
            <label className="app-field">
              <span>Task</span>
              <select
                value={assignmentDraft.task_id}
                onChange={(event) =>
                  setAssignmentDraft((previous) => ({
                    ...previous,
                    task_id: event.target.value,
                  }))
                }
                required
              >
                {tasks.length === 0 ? <option value="">No tasks</option> : null}
                {tasks.map((task) => (
                  <option key={task.id} value={task.id}>
                    {task.code} — {task.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="app-field">
              <span>Performer</span>
              <select
                value={assignmentDraft.performer_id}
                onChange={(event) =>
                  setAssignmentDraft((previous) => ({
                    ...previous,
                    performer_id: event.target.value,
                  }))
                }
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
          </div>
          <div className="app-row">
            <button
              type="submit"
              disabled={
                !assignmentDraft.task_id ||
                !assignmentDraft.performer_id ||
                assignmentKeySet.has(`${assignmentDraft.task_id}:${assignmentDraft.performer_id}`)
              }
            >
              Add assignment
            </button>
          </div>
          <ul className="app-list">
            {assignments.map((assignment) => (
              <li key={`${assignment.task_id}:${assignment.performer_id}`}>
                <span>
                  {taskById.get(assignment.task_id)?.code ?? assignment.task_id} →{" "}
                  {performerById.get(assignment.performer_id)?.display_name ?? assignment.performer_id}
                </span>
                <button
                  type="button"
                  className="app-button-danger"
                  onClick={() => void onDeleteAssignment(assignment.task_id, assignment.performer_id)}
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
        </form>
      </div>
    </section>
  );
}
