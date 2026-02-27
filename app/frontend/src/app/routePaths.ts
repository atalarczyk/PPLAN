export const routePaths = {
  signIn: "/auth/sign-in",
  authCallback: "/auth/callback",
  unauthorized: "/unauthorized",
  forbidden: "/forbidden",
  projects: "/projects",
  admin: "/admin",
  businessUnitDashboard: (businessUnitId: string) => `/business-units/${businessUnitId}/dashboard`,
  projectMatrix: (projectId: string) => `/projects/${projectId}/matrix`,
  projectFinance: (projectId: string) => `/projects/${projectId}/finance`,
  projectReports: (projectId: string) => `/projects/${projectId}/reports`,
  projectDashboard: (projectId: string) => `/projects/${projectId}/dashboard`,
  projectSettings: (projectId: string) => `/projects/${projectId}/settings`,
};
