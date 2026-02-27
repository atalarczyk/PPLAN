import { Navigate, createBrowserRouter, RouterProvider } from "react-router-dom";

import { AppShell } from "./shell";
import { routePaths } from "./routePaths";
import { ProtectedRoute } from "./auth/routeGuards";
import { AuthCallbackPage, ForbiddenPage, SignInPage, UnauthorizedPage } from "./auth/views";
import { AdminPage } from "../features/admin/AdminPage";
import { BusinessUnitDashboardPage } from "../features/dashboard/BusinessUnitDashboardPage";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { FinancePage } from "../features/finance/FinancePage";
import { MatrixPage } from "../features/matrix/MatrixPage";
import { ProjectsPage } from "../features/projects/ProjectsPage";
import { ProjectSettingsPage } from "../features/projects/ProjectSettingsPage";
import { ReportsPage } from "../features/reports/ReportsPage";

const router = createBrowserRouter([
  {
    path: routePaths.signIn,
    element: <SignInPage />,
  },
  {
    path: routePaths.authCallback,
    element: <AuthCallbackPage />,
  },
  {
    path: routePaths.unauthorized,
    element: <UnauthorizedPage />,
  },
  {
    path: routePaths.forbidden,
    element: <ForbiddenPage />,
  },
  {
    path: "/",
    element: (
      <ProtectedRoute>
        <AppShell />
      </ProtectedRoute>
    ),
    children: [
      { index: true, element: <Navigate to={routePaths.projects} replace /> },
      {
        path: routePaths.projects,
        element: (
          <ProtectedRoute requirements={{ permission: "projects.read" }}>
            <ProjectsPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "business-units/:businessUnitId/dashboard",
        element: (
          <ProtectedRoute requirements={{ permission: "dashboards.view", requireScope: "businessUnit" }}>
            <BusinessUnitDashboardPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "projects/:projectId/matrix",
        element: (
          <ProtectedRoute requirements={{ permission: "matrix.edit", requireScope: "project" }}>
            <MatrixPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "projects/:projectId/finance",
        element: (
          <ProtectedRoute requirements={{ permission: "finance.edit", requireScope: "project" }}>
            <FinancePage />
          </ProtectedRoute>
        ),
      },
      {
        path: "projects/:projectId/reports",
        element: (
          <ProtectedRoute requirements={{ permission: "reports.view", requireScope: "project" }}>
            <ReportsPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "projects/:projectId/dashboard",
        element: (
          <ProtectedRoute requirements={{ permission: "dashboards.view", requireScope: "project" }}>
            <DashboardPage />
          </ProtectedRoute>
        ),
      },
      {
        path: "projects/:projectId/settings",
        element: (
          <ProtectedRoute requirements={{ permission: "projects.write", requireScope: "project" }}>
            <ProjectSettingsPage />
          </ProtectedRoute>
        ),
      },
      {
        path: routePaths.admin,
        element: (
          <ProtectedRoute
            requirements={{ roles: ["super_admin", "business_unit_admin"], permission: "admin.view" }}
          >
            <AdminPage />
          </ProtectedRoute>
        ),
      },
    ],
  },
  {
    path: "*",
    element: <Navigate to={routePaths.projects} replace />,
  },
]);

export const DEFAULT_DEMO_ROUTE = routePaths.projects;

export function AppRouter() {
  return <RouterProvider router={router} />;
}

