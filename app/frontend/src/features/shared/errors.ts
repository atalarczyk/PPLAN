import { ApiError } from "../../app/api/http";

function extractApiDetail(payload: unknown): string | null {
  if (typeof payload === "string" && payload.trim().length > 0) {
    return payload;
  }

  if (payload && typeof payload === "object") {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim().length > 0) {
      return detail;
    }
  }

  return null;
}

export function toErrorMessage(error: unknown, fallback = "Unexpected error occurred."): string {
  if (error instanceof ApiError) {
    return extractApiDetail(error.payload) ?? `${error.message} (HTTP ${error.status})`;
  }

  if (error instanceof Error && error.message.trim().length > 0) {
    return error.message;
  }

  return fallback;
}

