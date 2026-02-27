const DEFAULT_API_BASE_URL = "/api/v1";

type AccessTokenProvider = () => Promise<string | null> | string | null;

export type QueryPrimitive = string | number | boolean;
export type QueryValue = QueryPrimitive | QueryPrimitive[] | null | undefined;
export type QueryParams = Record<string, QueryValue>;
export type ApiResponseType = "json" | "text" | "blob" | "none";

export interface ApiRequestOptions extends Omit<RequestInit, "method" | "body"> {
  query?: QueryParams;
  body?: unknown;
  responseType?: ApiResponseType;
}

let accessTokenProvider: AccessTokenProvider | null = null;

export class ApiError extends Error {
  readonly status: number;
  readonly payload: unknown;

  constructor(message: string, status: number, payload: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.payload = payload;
  }
}

export function configureApiAccessTokenProvider(provider: AccessTokenProvider | null): void {
  accessTokenProvider = provider;
}

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
}

export function resolveApiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL?.trim();
  if (configured && configured.length > 0) {
    return normalizeBaseUrl(configured);
  }
  return DEFAULT_API_BASE_URL;
}

async function parseErrorPayload(response: Response): Promise<unknown> {
  try {
    return await response.json();
  } catch {
    try {
      return await response.text();
    } catch {
      return null;
    }
  }
}

function appendQueryParams(path: string, query?: QueryParams): string {
  if (!query) {
    return path;
  }

  const hasQueryString = path.includes("?");
  const params = new URLSearchParams(hasQueryString ? path.split("?")[1] : "");
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) {
      continue;
    }

    if (Array.isArray(value)) {
      for (const item of value) {
        params.append(key, String(item));
      }
      continue;
    }

    params.append(key, String(value));
  }

  const cleanPath = hasQueryString ? path.split("?")[0] : path;
  const queryString = params.toString();
  return queryString.length > 0 ? `${cleanPath}?${queryString}` : cleanPath;
}

function toBodyInit(payload: unknown, headers: Headers): BodyInit | undefined {
  if (payload === undefined || payload === null) {
    return undefined;
  }

  if (
    typeof payload === "string" ||
    payload instanceof URLSearchParams ||
    payload instanceof Blob ||
    payload instanceof ArrayBuffer ||
    ArrayBuffer.isView(payload) ||
    (typeof FormData !== "undefined" && payload instanceof FormData)
  ) {
    return payload as BodyInit;
  }

  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return JSON.stringify(payload);
}

function withDefaultAcceptHeader(headers: Headers, responseType: ApiResponseType): void {
  if (headers.has("Accept")) {
    return;
  }

  if (responseType === "json") {
    headers.set("Accept", "application/json");
    return;
  }

  if (responseType === "text") {
    headers.set("Accept", "text/plain");
    return;
  }

  headers.set("Accept", "*/*");
}

async function attachAuthorizationHeader(headers: Headers): Promise<void> {
  if (!accessTokenProvider || headers.has("Authorization")) {
    return;
  }

  const token = await accessTokenProvider();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
}

async function parseSuccessPayload<TResponse>(
  response: Response,
  responseType: ApiResponseType,
): Promise<TResponse> {
  if (responseType === "none" || response.status === 204) {
    return undefined as TResponse;
  }

  if (responseType === "text") {
    return (await response.text()) as TResponse;
  }

  if (responseType === "blob") {
    return (await response.blob()) as TResponse;
  }

  const contentType = response.headers.get("Content-Type")?.toLowerCase() ?? "";
  if (!contentType.includes("application/json")) {
    const text = await response.text();
    if (text.length === 0) {
      return undefined as TResponse;
    }

    try {
      return JSON.parse(text) as TResponse;
    } catch {
      return text as TResponse;
    }
  }

  return (await response.json()) as TResponse;
}

export async function apiRequestRaw(
  method: string,
  path: string,
  options: Omit<ApiRequestOptions, "responseType"> = {},
): Promise<Response> {
  const { query, body, ...init } = options;
  const requestPath = appendQueryParams(path, query);

  const headers = new Headers(init.headers);
  withDefaultAcceptHeader(headers, "json");
  await attachAuthorizationHeader(headers);

  const response = await fetch(`${resolveApiBaseUrl()}${requestPath}`, {
    ...init,
    method,
    credentials: "include",
    headers,
    body: toBodyInit(body, headers),
  });

  if (!response.ok) {
    const payload = await parseErrorPayload(response);
    throw new ApiError(`${method.toUpperCase()} ${requestPath} failed`, response.status, payload);
  }

  return response;
}

export async function apiRequest<TResponse>(
  method: string,
  path: string,
  options: ApiRequestOptions = {},
): Promise<TResponse> {
  const { responseType = "json", query, body, ...init } = options;
  const requestPath = appendQueryParams(path, query);

  const headers = new Headers(init.headers);
  withDefaultAcceptHeader(headers, responseType);
  await attachAuthorizationHeader(headers);

  const response = await fetch(`${resolveApiBaseUrl()}${requestPath}`, {
    ...init,
    method,
    credentials: "include",
    headers,
    body: toBodyInit(body, headers),
  });

  if (!response.ok) {
    const payload = await parseErrorPayload(response);
    throw new ApiError(`${method.toUpperCase()} ${requestPath} failed`, response.status, payload);
  }

  return parseSuccessPayload<TResponse>(response, responseType);
}

export async function apiGet<TResponse>(path: string, options: ApiRequestOptions = {}): Promise<TResponse> {
  return apiRequest<TResponse>("GET", path, options);
}

export async function apiPost<TResponse>(path: string, options: ApiRequestOptions = {}): Promise<TResponse> {
  return apiRequest<TResponse>("POST", path, options);
}

export async function apiPut<TResponse>(path: string, options: ApiRequestOptions = {}): Promise<TResponse> {
  return apiRequest<TResponse>("PUT", path, options);
}

export async function apiPatch<TResponse>(path: string, options: ApiRequestOptions = {}): Promise<TResponse> {
  return apiRequest<TResponse>("PATCH", path, options);
}

export async function apiDelete(path: string, options: ApiRequestOptions = {}): Promise<void> {
  await apiRequest<void>("DELETE", path, {
    ...options,
    responseType: "none",
  });
}
