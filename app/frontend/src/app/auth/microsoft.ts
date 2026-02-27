import { configureApiAccessTokenProvider } from "../api/http";

interface MicrosoftAuthConfig {
  tenantId: string;
  clientId: string;
}

function readMicrosoftAuthConfig(): MicrosoftAuthConfig {
  return {
    tenantId: import.meta.env.VITE_MICROSOFT_TENANT_ID ?? "",
    clientId: import.meta.env.VITE_MICROSOFT_CLIENT_ID ?? "",
  };
}

function hasUsableConfig(config: MicrosoftAuthConfig): boolean {
  return config.tenantId.trim().length > 0 && config.clientId.trim().length > 0;
}

let initialized = false;

export function initializeMicrosoftAuthBridge(): void {
  if (initialized) {
    return;
  }

  const config = readMicrosoftAuthConfig();
  if (!hasUsableConfig(config)) {
    initialized = true;
    return;
  }

  // Placeholder bridge:
  // - currently relies on backend trusted-header/dev principal behavior
  // - later milestone will replace with MSAL token acquisition and refresh logic
  // - API layer already supports Authorization injection via provider callback
  configureApiAccessTokenProvider(async () => null);
  initialized = true;
}

