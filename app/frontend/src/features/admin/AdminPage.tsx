import { useEffect, useMemo, useState, type FormEvent } from "react";

import { useAuth } from "../../app/auth/AuthProvider";
import { toErrorMessage } from "../shared/errors";
import {
  createBusinessUnit,
  createRoleAssignment,
  listBusinessUnits,
  listUsers,
  updateBusinessUnit,
  updateRoleAssignment,
  type AppRole,
  type BusinessUnitRecord,
  type UserRecord,
} from "./api";

interface BusinessUnitDraft {
  code: string;
  name: string;
  active: boolean;
}

interface RoleAssignmentDraft {
  user_email: string;
  user_display_name: string;
  user_microsoft_oid: string;
  role: AppRole;
  business_unit_id: string;
  active: boolean;
}

const DEFAULT_BUSINESS_UNIT_DRAFT: BusinessUnitDraft = {
  code: "",
  name: "",
  active: true,
};

const DEFAULT_ASSIGNMENT_DRAFT: RoleAssignmentDraft = {
  user_email: "",
  user_display_name: "",
  user_microsoft_oid: "",
  role: "viewer",
  business_unit_id: "",
  active: true,
};

export function AdminPage() {
  const { state, hasRole } = useAuth();

  const [businessUnits, setBusinessUnits] = useState<BusinessUnitRecord[]>([]);
  const [users, setUsers] = useState<UserRecord[]>([]);

  const [businessUnitDraft, setBusinessUnitDraft] = useState<BusinessUnitDraft>(DEFAULT_BUSINESS_UNIT_DRAFT);
  const [assignmentDraft, setAssignmentDraft] = useState<RoleAssignmentDraft>(DEFAULT_ASSIGNMENT_DRAFT);

  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const isSuperAdmin = hasRole(["super_admin"]);
  const isBusinessUnitAdmin = hasRole(["business_unit_admin"]);

  const assignmentRoleOptions = useMemo<AppRole[]>(() => {
    if (isSuperAdmin) {
      return ["super_admin", "business_unit_admin", "editor", "viewer"];
    }
    return ["business_unit_admin", "editor", "viewer"];
  }, [isSuperAdmin]);

  useEffect(() => {
    let cancelled = false;

    async function loadData() {
      setLoading(true);
      setErrorMessage(null);

      try {
        const [unitRows, userRows] = await Promise.all([listBusinessUnits(), listUsers()]);

        if (cancelled) {
          return;
        }

        setBusinessUnits(unitRows);
        setUsers(userRows);
        setAssignmentDraft((previous) => ({
          ...previous,
          business_unit_id: previous.business_unit_id || unitRows[0]?.id || "",
        }));
      } catch (error) {
        if (!cancelled) {
          setErrorMessage(toErrorMessage(error, "Unable to load admin data."));
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
  }, []);

  async function refresh() {
    setLoading(true);
    setErrorMessage(null);
    try {
      const [unitRows, userRows] = await Promise.all([listBusinessUnits(), listUsers()]);
      setBusinessUnits(unitRows);
      setUsers(userRows);
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to refresh admin data."));
    } finally {
      setLoading(false);
    }
  }

  async function onCreateBusinessUnit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isSuperAdmin) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await createBusinessUnit({
        code: businessUnitDraft.code.trim(),
        name: businessUnitDraft.name.trim(),
        active: businessUnitDraft.active,
      });
      setBusinessUnitDraft(DEFAULT_BUSINESS_UNIT_DRAFT);
      await refresh();
      setSuccessMessage("Business unit created.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to create business unit."));
    }
  }

  async function onToggleBusinessUnitActive(unit: BusinessUnitRecord) {
    if (!isSuperAdmin) {
      return;
    }

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await updateBusinessUnit(unit.id, {
        active: !unit.active,
      });
      await refresh();
      setSuccessMessage(`Business unit ${unit.code} updated.`);
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to update business unit."));
    }
  }

  async function onCreateRoleAssignment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await createRoleAssignment({
        user_email: assignmentDraft.user_email.trim(),
        user_display_name: assignmentDraft.user_display_name.trim() || undefined,
        user_microsoft_oid: assignmentDraft.user_microsoft_oid.trim(),
        role: assignmentDraft.role,
        business_unit_id: assignmentDraft.role === "super_admin" ? null : assignmentDraft.business_unit_id,
        active: assignmentDraft.active,
      });
      setAssignmentDraft((previous) => ({
        ...DEFAULT_ASSIGNMENT_DRAFT,
        business_unit_id: previous.business_unit_id,
      }));
      await refresh();
      setSuccessMessage("Role assignment created.");
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to create role assignment."));
    }
  }

  async function onToggleRoleAssignmentActive(userId: string, assignmentId: string, active: boolean) {
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await updateRoleAssignment(assignmentId, {
        active: !active,
      });
      await refresh();
      setSuccessMessage(`Assignment for user ${userId} updated.`);
    } catch (error) {
      setErrorMessage(toErrorMessage(error, "Unable to update role assignment."));
    }
  }

  return (
    <section>
      <div className="app-row app-row-spaced">
        <div>
          <h2>Administration</h2>
          <p>Manage business units and role assignments.</p>
        </div>
        <button type="button" onClick={() => void refresh()} disabled={loading}>
          Refresh
        </button>
      </div>

      {loading ? <p className="app-state">Loading admin data…</p> : null}
      {errorMessage ? <p className="app-state app-error">{errorMessage}</p> : null}
      {successMessage ? <p className="app-state app-success">{successMessage}</p> : null}

      <div className="app-grid app-grid-2">
        <div className="app-form">
          <h3>Business units</h3>
          {isSuperAdmin ? (
            <form onSubmit={onCreateBusinessUnit} className="app-form-inner">
              <div className="app-grid app-grid-3">
                <label className="app-field">
                  <span>Code</span>
                  <input
                    value={businessUnitDraft.code}
                    onChange={(event) =>
                      setBusinessUnitDraft((previous) => ({
                        ...previous,
                        code: event.target.value,
                      }))
                    }
                    required
                  />
                </label>
                <label className="app-field">
                  <span>Name</span>
                  <input
                    value={businessUnitDraft.name}
                    onChange={(event) =>
                      setBusinessUnitDraft((previous) => ({
                        ...previous,
                        name: event.target.value,
                      }))
                    }
                    required
                  />
                </label>
                <label className="app-field">
                  <span>Active</span>
                  <select
                    value={businessUnitDraft.active ? "true" : "false"}
                    onChange={(event) =>
                      setBusinessUnitDraft((previous) => ({
                        ...previous,
                        active: event.target.value === "true",
                      }))
                    }
                  >
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </label>
              </div>
              <div className="app-row">
                <button type="submit">Create business unit</button>
              </div>
            </form>
          ) : (
            <p className="app-state">Business-unit creation is super-admin only.</p>
          )}

          <table className="app-table">
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Active</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {businessUnits.map((unit) => (
                <tr key={unit.id}>
                  <td>{unit.code}</td>
                  <td>{unit.name}</td>
                  <td>{unit.active ? "yes" : "no"}</td>
                  <td>
                    {isSuperAdmin ? (
                      <button
                        type="button"
                        className="app-button-secondary"
                        onClick={() => void onToggleBusinessUnitActive(unit)}
                      >
                        {unit.active ? "Deactivate" : "Activate"}
                      </button>
                    ) : (
                      <span className="app-nav-disabled">Read-only</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="app-form">
          <h3>Role assignments</h3>
          {(isSuperAdmin || isBusinessUnitAdmin) ? (
            <form onSubmit={onCreateRoleAssignment} className="app-form-inner">
              <div className="app-grid app-grid-2">
                <label className="app-field">
                  <span>User email</span>
                  <input
                    type="email"
                    value={assignmentDraft.user_email}
                    onChange={(event) =>
                      setAssignmentDraft((previous) => ({
                        ...previous,
                        user_email: event.target.value,
                      }))
                    }
                    required
                  />
                </label>
                <label className="app-field">
                  <span>User display name</span>
                  <input
                    value={assignmentDraft.user_display_name}
                    onChange={(event) =>
                      setAssignmentDraft((previous) => ({
                        ...previous,
                        user_display_name: event.target.value,
                      }))
                    }
                  />
                </label>
                <label className="app-field">
                  <span>User Microsoft OID</span>
                  <input
                    value={assignmentDraft.user_microsoft_oid}
                    onChange={(event) =>
                      setAssignmentDraft((previous) => ({
                        ...previous,
                        user_microsoft_oid: event.target.value,
                      }))
                    }
                    required
                  />
                </label>
                <label className="app-field">
                  <span>Role</span>
                  <select
                    value={assignmentDraft.role}
                    onChange={(event) =>
                      setAssignmentDraft((previous) => ({
                        ...previous,
                        role: event.target.value as AppRole,
                      }))
                    }
                  >
                    {assignmentRoleOptions.map((role) => (
                      <option key={role} value={role}>
                        {role}
                      </option>
                    ))}
                  </select>
                </label>

                {assignmentDraft.role !== "super_admin" ? (
                  <label className="app-field">
                    <span>Business unit</span>
                    <select
                      value={assignmentDraft.business_unit_id}
                      onChange={(event) =>
                        setAssignmentDraft((previous) => ({
                          ...previous,
                          business_unit_id: event.target.value,
                        }))
                      }
                      required
                    >
                      {businessUnits.map((unit) => (
                        <option key={unit.id} value={unit.id}>
                          {unit.code} — {unit.name}
                        </option>
                      ))}
                    </select>
                  </label>
                ) : null}
              </div>

              <div className="app-row">
                <button
                  type="submit"
                  disabled={assignmentDraft.role !== "super_admin" && !assignmentDraft.business_unit_id}
                >
                  Create assignment
                </button>
              </div>
            </form>
          ) : (
            <p className="app-state">No permissions for assignment management.</p>
          )}

          <table className="app-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Business unit</th>
                <th>Active</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? (
                <tr>
                  <td colSpan={5}>No users in visible scope.</td>
                </tr>
              ) : (
                users.flatMap((user) =>
                  user.role_assignments.map((assignment) => (
                    <tr key={assignment.id}>
                      <td>{user.email}</td>
                      <td>{assignment.role}</td>
                      <td>
                        {assignment.business_unit_id
                          ? businessUnits.find((unit) => unit.id === assignment.business_unit_id)?.code ?? assignment.business_unit_id
                          : "global"}
                      </td>
                      <td>{assignment.active ? "yes" : "no"}</td>
                      <td>
                        {(isSuperAdmin || isBusinessUnitAdmin) ? (
                          <button
                            type="button"
                            className="app-button-secondary"
                            onClick={() => void onToggleRoleAssignmentActive(user.id, assignment.id, assignment.active)}
                          >
                            {assignment.active ? "Disable" : "Enable"}
                          </button>
                        ) : (
                          <span className="app-nav-disabled">Read-only</span>
                        )}
                      </td>
                    </tr>
                  )),
                )
              )}
            </tbody>
          </table>
        </div>
      </div>

      <p className="app-state app-muted">
        Signed in as {state.session?.user.email ?? "unknown"}.
      </p>
    </section>
  );
}

