import { apiRequestRaw, type QueryParams } from "../../app/api/http";
import type { ReportKey } from "../reports/api";

export type ExportFormat = "csv" | "xlsx";

export interface ExportReportInput {
  reportKey: ReportKey;
  format: ExportFormat;
  projectId: string;
  fromMonth?: string;
  toMonth?: string;
  performerIds?: string[];
  taskIds?: string[];
}

export interface ExportFilePayload {
  filename: string;
  contentType: string;
  content: Blob;
}

function parseFilenameFromContentDisposition(headerValue: string | null): string | null {
  if (!headerValue) {
    return null;
  }

  const utf8Match = headerValue.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]);
  }

  const quotedMatch = headerValue.match(/filename="([^"]+)"/i);
  if (quotedMatch?.[1]) {
    return quotedMatch[1];
  }

  const bareMatch = headerValue.match(/filename=([^;]+)/i);
  if (bareMatch?.[1]) {
    return bareMatch[1].trim();
  }

  return null;
}

function buildExportQuery(input: ExportReportInput): QueryParams {
  return {
    project_id: input.projectId,
    format: input.format,
    from_month: input.fromMonth,
    to_month: input.toMonth,
    performer_id: input.performerIds,
    task_id: input.taskIds,
  };
}

export async function exportReport(input: ExportReportInput): Promise<ExportFilePayload> {
  const response = await apiRequestRaw("GET", `/exports/${input.reportKey}`, {
    query: buildExportQuery(input),
  });

  const filename =
    parseFilenameFromContentDisposition(response.headers.get("Content-Disposition")) ??
    `${input.reportKey}.${input.format}`;

  return {
    filename,
    contentType: response.headers.get("Content-Type") ?? "application/octet-stream",
    content: await response.blob(),
  };
}

