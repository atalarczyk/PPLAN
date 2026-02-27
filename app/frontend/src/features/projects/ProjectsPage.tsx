import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import { routePaths } from "../../app/routePaths";
import { useAuth } from "../../app/auth/AuthProvider";
import { listBusinessUnits } from "../admin/api";
import { toErrorMessage } from "../shared/errors";
import {
  createBusinessUnitProject,
  deleteProject,
  listBusinessUnitProjects,
  type ProjectRecord,
  type ProjectStatus,
  updateProject,
} from "./api";

interface BusinessUnitOption {
  id: string;
  label: string;
}

interface ProjectDraft {
  code: string;
  name: string;
  description: string;
  start_month: string;
  end_month: string;
  status: ProjectStatus;
}

const DEFAULT_DRAFT: ProjectDraft = {
  code: "",
  name: "",
  description: "",
  start_month: "",
  end_month: "",
  status: "draft",
};

export function ProjectsPage() {
  const { state, hasPermission } = useAuth();
  const [businessUnitOptions, setBusinessUnitOptions] = useState<BusinessUnitOption[]>([]);
  const [selectedBusinessUnitId, setSelectedBusinessUnitId] = useState<string>("");

  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [loadingBusinessUnits, setLoadingBusinessUnits] = useState(true);
  const [loadingProjects, setLoadingProjects] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [createDraft, setCreateDraft] = useState<ProjectDraft>(DEFAULT_DRAFT);
  const [editingProjectId, setEditingProjectId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<ProjectDraft>(DEFAULT_DRAFT);

  const canViewAdminMetadata = hasPermission("admin.view");
  const canCreateProject = selectedBusinessUnitId
    ? hasPermission("projects.write", { businessUnitId: selectedBusinessUnitId })
    : false;

  const selectedBusinessUnitLabel = useMemo(() => {
    const option = businessUnitOptions.find((item) => item.id === selectedBusinessUnitId);
    return option?.label ?? selectedBusinessUnitId;
  }, [businessUnitOptions, selectedBusinessUnitId]);

  useEffect(() => {
    let cancelled = false;

    async function loadBusinessUnitOptions() {
      setLoadingBusinessUnits(true);
      setErrorMessage(null);

      const scopedFallback: BusinessUnitOption[] =
        state.session?.businessUnitIds.map((businessUnitId) => ({
          id: businessUnitId,
          label: businessUnitId,
        })) ?? [];

      try {
        if (canViewAdminMetadata) {
          const units = await listBusinessUnits();
          if (cancelled) {
            return;
          }

          const nextOptions = units.map((unit) => ({
            id: unit.id,
            label: `${unit.code} — ${unit.name}`,
          }));
          setBusinessUnitOptions(nextOptions);
          if (nextOptions.length > 0) {
            setSelectedBusinessUnitId((current) =>
              current && nextOptions.some((option) => option.id === current) ? current : nextOptions[0].id,
            );
          }
          return;
        }

        setBusinessUnitOptions(scopedFallback);
        if (scopedFallback.length > 0) {
          setSelectedBusinessUnitId((current) =>
            current && scopedFallback.some((option) => option.id === current) ? current : scopedFallback[0].id,
          );
        }
      } catch (error) {
        if (cancelled) {
          return;
        }

        setBusinessUnitOptions(scopedFallback);
        if (scopedFallback.length > 0) {
          setSelectedBusinessUnitId(scopedFallback[0].id);
        }
        setErrorMessage(toErrorMessage(error, "Unable to load business-unit context."));
      } finally {
        if (!cancelled) {
          setLoadingBusinessUnits(false);
        }
      }
    }

    void loadBusinessUnitOptions();
    return () => {
      cancelled = true;
    };
  }, [state.session, canViewAdminMetadata]);

  useEffect(() => {
    let cancelled = false;

    async function loadProjects() {
      if (!selectedBusinessUnitId) {
        setProjects([]);
        return;
      }

      setLoadingProjects(true);
      setErrorMessage(null);
      try {
        const listed = await listBusinessUnitProjects(selectedBusinessUnitId);
        if (!cancelled) {
          setProjects(listed);
        }
      } catch (error) {
        if (!cancelled) {
          setProjects([]);
          setErrorMessage(toErrorMessage(error, "Unable to load projects."));
        }
      } finally {
        if (!cancelled) {
          setLoadingProjects(false);
        }
      }
    }

    void loadProjects();
    return () => {
      cancelled = true;
    };
  }, [selectedBusinessUnitId]);

  async function refreshProjects(): Promise<void> {
    if (!selectedBusinessUnitId) {
      setProjects([]);
      return;
    }

    setLoadingProjects(true);
    setErrorMessage(null);
    try {
      const listed = await listBusinessUnitProjects(selectedBusinessUnitId);
      setProjects(listed);
    } catch (error) {
      setProjects([]);
      setErrorMessage(toErrorMessage(error, "Unable to refresh projects."));
    } finally {
      setLoadingProjects(false);
    }
  }

  async function onCreateProjectSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedBusinessUnitId || !canCreateProject) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await createBusinessUnitProject(selectedBusinessUnitId, {
        ...createDraft,
        description: createDraft.description.trim() || null,
      });
      setCreateDraft(DEFAULT_DRAFT);
      await refreshProjects();
      setSuccessMessage("Project created successfully.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to create project."));
    }
  }

  function beginProjectEdit(project: ProjectRecord) {
    setEditingProjectId(project.id);
    setEditDraft({
      code: project.code,
      name: project.name,
      description: project.description ?? "",
      start_month: project.start_month.slice(0, 10),
      end_month: project.end_month.slice(0, 10),
      status: project.status,
    });
  }

  async function onSaveProjectEdit(projectId: string) {
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await updateProject(projectId, {
        ...editDraft,
        description: editDraft.description.trim() || null,
      });
      setEditingProjectId(null);
      await refreshProjects();
      setSuccessMessage("Project updated successfully.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to update project."));
    }
  }

  async function onDeleteProject(projectId: string) {
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await deleteProject(projectId);
      await refreshProjects();
      setSuccessMessage("Project deleted successfully.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to delete project."));
    }
  }

  return (
    <section>
      <h2>Projects</h2>
      <p>Manage project portfolio in selected business-unit scope.</p>

      <div className="app-row">
        <label className="app-field">
          <span>Business unit scope</span>
          <select
            value={selectedBusinessUnitId}
            onChange={(event) => setSelectedBusinessUnitId(event.target.value)}
            disabled={loadingBusinessUnits || businessUnitOptions.length === 0}
          >
            {businessUnitOptions.length === 0 ? (
              <option value="">No business units available</option>
            ) : (
              businessUnitOptions.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))
            )}
          </select>
        </label>
      </div>

      {loadingBusinessUnits ? <p className="app-state">Loading business units…</p> : null}
      {errorMessage ? <p className="app-state app-error">{errorMessage}</p> : null}
      {successMessage ? <p className="app-state app-success">{successMessage}</p> : null}

      {selectedBusinessUnitId && canCreateProject ? (
        <form className="app-form" onSubmit={onCreateProjectSubmit}>
          <h3>Create project</h3>
          <div className="app-grid app-grid-3">
            <label className="app-field">
              <span>Code</span>
              <input
                value={createDraft.code}
                onChange={(event) => setCreateDraft((previous) => ({ ...previous, code: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>Name</span>
              <input
                value={createDraft.name}
                onChange={(event) => setCreateDraft((previous) => ({ ...previous, name: event.target.value }))}
                required
              />
            </label>
            <label className="app-field">
              <span>Status</span>
              <select
                value={createDraft.status}
                onChange={(event) =>
                  setCreateDraft((previous) => ({
                    ...previous,
                    status: event.target.value as ProjectStatus,
                  }))
                }
              >
                <option value="draft">draft</option>
                <option value="active">active</option>
                <option value="closed">closed</option>
              </select>
            </label>
            <label className="app-field">
              <span>Start month</span>
              <input
                type="date"
                value={createDraft.start_month}
                onChange={(event) =>
                  setCreateDraft((previous) => ({
                    ...previous,
                    start_month: event.target.value,
                  }))
                }
                required
              />
            </label>
            <label className="app-field">
              <span>End month</span>
              <input
                type="date"
                value={createDraft.end_month}
                onChange={(event) =>
                  setCreateDraft((previous) => ({
                    ...previous,
                    end_month: event.target.value,
                  }))
                }
                required
              />
            </label>
            <label className="app-field app-field-full">
              <span>Description</span>
              <input
                value={createDraft.description}
                onChange={(event) =>
                  setCreateDraft((previous) => ({
                    ...previous,
                    description: event.target.value,
                  }))
                }
              />
            </label>
          </div>
          <div className="app-row">
            <button type="submit">Create project</button>
          </div>
        </form>
      ) : selectedBusinessUnitId ? (
        <p className="app-state">Project creation is disabled for current role in selected business unit.</p>
      ) : null}

      <div className="app-row app-row-spaced">
        <h3>Project list {selectedBusinessUnitLabel ? `— ${selectedBusinessUnitLabel}` : ""}</h3>
        <button type="button" onClick={() => void refreshProjects()} disabled={!selectedBusinessUnitId || loadingProjects}>
          Refresh
        </button>
      </div>

      {loadingProjects ? <p className="app-state">Loading projects…</p> : null}
      {!loadingProjects && selectedBusinessUnitId && projects.length === 0 ? (
        <p className="app-state">No projects found for selected business unit.</p>
      ) : null}

      {projects.length > 0 ? (
        <table className="app-table">
          <thead>
            <tr>
              <th>Code</th>
              <th>Name</th>
              <th>Status</th>
              <th>Range</th>
              <th>Workspaces</th>
              <th>Manage</th>
            </tr>
          </thead>
          <tbody>
            {projects.map((project) => {
              const canEditProject = hasPermission("projects.write", { businessUnitId: project.business_unit_id });
              const matrixEnabled = hasPermission("matrix.edit", { projectId: project.id });
              const financeEnabled = hasPermission("finance.edit", { projectId: project.id });
              const reportsEnabled = hasPermission("reports.view", { projectId: project.id });
              const dashboardEnabled = hasPermission("dashboards.view", { projectId: project.id });

              return (
                <tr key={project.id}>
                  <td>{project.code}</td>
                  <td>
                    {editingProjectId === project.id ? (
                      <input
                        value={editDraft.name}
                        onChange={(event) =>
                          setEditDraft((previous) => ({
                            ...previous,
                            name: event.target.value,
                          }))
                        }
                      />
                    ) : (
                      project.name
                    )}
                  </td>
                  <td>
                    {editingProjectId === project.id ? (
                      <select
                        value={editDraft.status}
                        onChange={(event) =>
                          setEditDraft((previous) => ({
                            ...previous,
                            status: event.target.value as ProjectStatus,
                          }))
                        }
                      >
                        <option value="draft">draft</option>
                        <option value="active">active</option>
                        <option value="closed">closed</option>
                      </select>
                    ) : (
                      project.status
                    )}
                  </td>
                  <td>
                    {project.start_month.slice(0, 7)} → {project.end_month.slice(0, 7)}
                  </td>
                  <td>
                    <div className="app-link-grid">
                      {matrixEnabled ? (
                        <Link to={routePaths.projectMatrix(project.id)}>Matrix</Link>
                      ) : (
                        <span className="app-nav-disabled">Matrix</span>
                      )}
                      {financeEnabled ? (
                        <Link to={routePaths.projectFinance(project.id)}>Finance</Link>
                      ) : (
                        <span className="app-nav-disabled">Finance</span>
                      )}
                      {reportsEnabled ? (
                        <Link to={routePaths.projectReports(project.id)}>Reports</Link>
                      ) : (
                        <span className="app-nav-disabled">Reports</span>
                      )}
                      {dashboardEnabled ? (
                        <Link to={routePaths.projectDashboard(project.id)}>Dashboard</Link>
                      ) : (
                        <span className="app-nav-disabled">Dashboard</span>
                      )}
                      {canEditProject ? (
                        <Link to={routePaths.projectSettings(project.id)}>Settings</Link>
                      ) : (
                        <span className="app-nav-disabled">Settings</span>
                      )}
                    </div>
                  </td>
                  <td>
                    <div className="app-row app-row-wrap">
                      {canEditProject && editingProjectId !== project.id ? (
                        <button type="button" onClick={() => beginProjectEdit(project)}>
                          Edit
                        </button>
                      ) : null}
                      {canEditProject && editingProjectId === project.id ? (
                        <>
                          <button type="button" onClick={() => void onSaveProjectEdit(project.id)}>
                            Save
                          </button>
                          <button type="button" className="app-button-secondary" onClick={() => setEditingProjectId(null)}>
                            Cancel
                          </button>
                        </>
                      ) : null}
                      {canEditProject ? (
                        <button
                          type="button"
                          className="app-button-danger"
                          onClick={() => void onDeleteProject(project.id)}
                        >
                          Delete
                        </button>
                      ) : (
                        <span className="app-nav-disabled">Read-only</span>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}

