import type {
  AnalysisRequest,
  AnalysisResponse,
  HealthResponse,
  ReportDetailResponse,
  ReportListResponse,
  RoleCatalogResponse
} from "@/types/api";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {})
    }
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `API request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>("/health"),
  roles: () => request<RoleCatalogResponse>("/roles"),
  runAnalysis: (payload: AnalysisRequest) =>
    request<AnalysisResponse>("/analysis", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  reports: () => request<ReportListResponse>("/reports"),
  report: (runId: string) => request<ReportDetailResponse>(`/reports/${runId}`)
};
