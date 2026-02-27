import { describe, expect, it, vi } from "vitest";

import { bulkUpsertMatrixEntries, getProjectMatrix } from "../features/matrix/api";
import { createProjectFinancialRequest, listProjectFinancialRequests } from "../features/finance/api";
import { exportReport } from "../features/exports/api";
import { createRoleAssignment, listBusinessUnits } from "../features/admin/api";
import { listBusinessUnitProjects } from "../features/projects/api";
import { evaluateProtectedRouteDecision } from "../app/auth/routeGuards";
import { clearProjectScopeRegistry } from "../app/auth/permissions";
import type { AuthState } from "../app/auth/types";

const projectId = "22222222-2222-2222-2222-222222222222";
const businessUnitId = "11111111-1111-1111-1111-111111111111";

function okJsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function createdJsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 201,
    headers: {
      "Content-Type": "application/json",
    },
  });
}

function authenticatedViewerState(): AuthState {
  return {
    status: "authenticated",
    session: {
      user: {
        id: "u-1",
        email: "viewer@test.local",
        displayName: "Viewer",
        status: "active",
        microsoftOid: "oid-viewer",
      },
      roles: ["viewer"],
      assignments: [{ role: "viewer", businessUnitId }],
      businessUnitIds: [businessUnitId],
      hasAccess: true,
    },
  };
}

describe("feature API clients", () => {
  it("loads matrix and sends bulk save payload", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        okJsonResponse({
          project: {
            id: projectId,
            business_unit_id: businessUnitId,
            code: "PRJ-1",
            name: "Project 1",
            description: null,
            start_month: "2026-01-01",
            end_month: "2026-03-01",
            status: "active",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
          months: ["2026-01-01"],
          stages: [],
          tasks: [],
          performers: [],
          assignments: [],
          entries: [],
          project_monthly_snapshots: [],
        }),
      )
      .mockResolvedValueOnce(
        okJsonResponse({
          updated_entries: 1,
          project_monthly_snapshots: [],
        }),
      );

    const matrix = await getProjectMatrix(projectId, {
      from_month: "2026-01-01",
      to_month: "2026-01-01",
    });
    expect(matrix.project.id).toBe(projectId);

    const result = await bulkUpsertMatrixEntries(projectId, [
      {
        task_id: "33333333-3333-3333-3333-333333333333",
        performer_id: "44444444-4444-4444-4444-444444444444",
        month_start: "2026-01-01",
        planned_person_days: "2.00",
        actual_person_days: "1.00",
      },
    ]);
    expect(result.updated_entries).toBe(1);

    const [, saveCall] = fetchMock.mock.calls;
    const savePath = String(saveCall[0]);
    const saveInit = saveCall[1] as RequestInit;

    expect(savePath).toContain(`/projects/${projectId}/matrix/entries/bulk`);
    expect(saveInit.method).toBe("PUT");
    expect(String(saveInit.body)).toContain("planned_person_days");

    fetchMock.mockRestore();
  });

  it("runs finance list + create flow via API clients", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(okJsonResponse({ items: [] }))
      .mockResolvedValueOnce(
        createdJsonResponse({
          id: "req-1",
          project_id: projectId,
          request_no: "REQ-1",
          request_date: "2026-01-15",
          month_start: "2026-01-01",
          amount: "100.00",
          currency: "PLN",
          status: "draft",
        }),
      );

    const listed = await listProjectFinancialRequests(projectId);
    expect(listed).toEqual([]);

    const created = await createProjectFinancialRequest(projectId, {
      request_no: "REQ-1",
      request_date: "2026-01-15",
      month_start: "2026-01-01",
      amount: "100.00",
      currency: "PLN",
      status: "draft",
    });
    expect(created.request_no).toBe("REQ-1");

    const [, createCall] = fetchMock.mock.calls;
    const createInit = createCall[1] as RequestInit;
    expect(createInit.method).toBe("POST");
    expect(String(createInit.body)).toContain("REQ-1");

    fetchMock.mockRestore();
  });

  it("downloads report export blob and extracts filename", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("a,b\n1,2\n", {
        status: 200,
        headers: {
          "Content-Type": "text/csv; charset=utf-8",
          "Content-Disposition": 'attachment; filename="effort-by-performer.csv"',
        },
      }),
    );

    const file = await exportReport({
      reportKey: "effort-by-performer",
      format: "csv",
      projectId,
    });

    expect(file.filename).toBe("effort-by-performer.csv");
    expect(file.contentType).toContain("text/csv");
    expect(await file.content.text()).toContain("a,b");

    fetchMock.mockRestore();
  });

  it("runs admin flow for units + assignment creation", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        okJsonResponse({
          items: [
            {
              id: businessUnitId,
              code: "BU-1",
              name: "Business Unit",
              active: true,
              created_at: "2026-01-01T00:00:00Z",
              updated_at: "2026-01-01T00:00:00Z",
            },
          ],
        }),
      )
      .mockResolvedValueOnce(
        createdJsonResponse({
          id: "assignment-1",
          user_id: "user-1",
          business_unit_id: businessUnitId,
          role: "viewer",
          active: true,
          created_at: "2026-01-01T00:00:00Z",
          updated_at: "2026-01-01T00:00:00Z",
        }),
      );

    const units = await listBusinessUnits();
    expect(units[0].id).toBe(businessUnitId);

    const assignment = await createRoleAssignment({
      user_email: "viewer@test.local",
      user_display_name: "Viewer",
      user_microsoft_oid: "oid-viewer",
      role: "viewer",
      business_unit_id: businessUnitId,
      active: true,
    });
    expect(assignment.role).toBe("viewer");

    const [, createCall] = fetchMock.mock.calls;
    const createPath = String(createCall[0]);
    const createInit = createCall[1] as RequestInit;
    expect(createPath).toContain("/users/role-assignments");
    expect(createInit.method).toBe("POST");
    expect(String(createInit.body)).toContain("viewer@test.local");

    fetchMock.mockRestore();
  });

  it("registers project scope from project-list API and unblocks project-scoped page guard", async () => {
    clearProjectScopeRegistry();
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      okJsonResponse({
        items: [
          {
            id: projectId,
            business_unit_id: businessUnitId,
            code: "PRJ-1",
            name: "Project 1",
            description: null,
            start_month: "2026-01-01",
            end_month: "2026-03-01",
            status: "active",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
        ],
      }),
    );

    const listed = await listBusinessUnitProjects(businessUnitId);
    expect(listed).toHaveLength(1);

    const decision = evaluateProtectedRouteDecision({
      state: authenticatedViewerState(),
      params: { projectId },
      requirements: {
        permission: "reports.view",
        requireScope: "project",
      },
    });
    expect(decision).toBe("allow");

    const [listCall] = fetchMock.mock.calls;
    const listPath = String(listCall[0]);
    expect(listPath).toContain(`/business-units/${businessUnitId}/projects`);

    fetchMock.mockRestore();
    clearProjectScopeRegistry();
  });
});
