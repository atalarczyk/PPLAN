import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { bootstrapAuthState } from "./bootstrap";
import { canAccessRoute, hasPermission, hasRole, type PermissionKey, type ScopeRequirement } from "./permissions";
import type { AppRole, AuthState } from "./types";

interface AuthContextValue {
  state: AuthState;
  refresh: () => Promise<void>;
  canAccessRoute: (requirements: {
    roles?: AppRole[];
    permission?: PermissionKey;
    scope?: ScopeRequirement;
  }) => boolean;
  hasRole: (roles: readonly AppRole[]) => boolean;
  hasPermission: (permission: PermissionKey, scope?: ScopeRequirement) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [state, setState] = useState<AuthState>({
    status: "loading",
    session: null,
  });

  const refresh = useCallback(async () => {
    setState((previousState) => ({
      ...previousState,
      status: "loading",
    }));

    const nextState = await bootstrapAuthState();
    setState(nextState);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const value = useMemo<AuthContextValue>(() => {
    return {
      state,
      refresh,
      canAccessRoute: (requirements) => canAccessRoute(state.session, requirements),
      hasRole: (roles) => hasRole(state.session, roles),
      hasPermission: (permission, scope) => hasPermission(state.session, { permission, scope }),
    };
  }, [state, refresh]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}

