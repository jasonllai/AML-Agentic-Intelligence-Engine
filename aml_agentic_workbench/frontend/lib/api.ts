import type {
  AnalysisRequest,
  AnalysisResponse,
  AnalysisStreamEvent,
  AnalysisStreamHandlers,
  CustomerDataResponse,
  CustomerDataSourcesResponse,
  EvaluationRunSummary,
  GoldenDatasetResponse,
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
  customerDataSources: () => request<CustomerDataSourcesResponse>("/customer-data/sources"),
  customerData: (customerId: string, source = "all", limit = 100) =>
    request<CustomerDataResponse>(
      `/customer-data/customer/${encodeURIComponent(customerId)}?source=${encodeURIComponent(source)}&limit=${limit}`
    ),
  runAnalysis: (payload: AnalysisRequest) =>
    request<AnalysisResponse>("/analysis", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  runAnalysisStream: (payload: AnalysisRequest, handlers: AnalysisStreamHandlers = {}) =>
    runAnalysisStream(payload, handlers),
  reports: () => request<ReportListResponse>("/reports"),
  report: (runId: string) => request<ReportDetailResponse>(`/reports/${runId}`),
  generateGoldenDataset: (caseLimit = 100) =>
    request<GoldenDatasetResponse>("/evaluations/generate-golden-dataset", {
      method: "POST",
      body: JSON.stringify({ case_limit: caseLimit })
    }),
  runEvaluation: (caseLimit = 20) =>
    request<EvaluationRunSummary>("/evaluations/run", {
      method: "POST",
      body: JSON.stringify({ case_limit: caseLimit })
    }),
  evaluations: () => request<EvaluationRunSummary[]>("/evaluations"),
  evaluation: (runId: string) => request<EvaluationRunSummary>(`/evaluations/${runId}`)
};

async function runAnalysisStream(
  payload: AnalysisRequest,
  handlers: AnalysisStreamHandlers
): Promise<AnalysisResponse> {
  const response = await fetch(`${API_BASE_URL}/analysis/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `API request failed with ${response.status}`);
  }
  if (!response.body) {
    throw new Error("Streaming response did not include a readable body.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResponse: AnalysisResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    for (const block of blocks) {
      const event = parseSseBlock(block);
      if (!event) continue;
      handlers.onEvent?.(event);
      if (event.event === "run_failed") {
        throw new Error(event.message || "Streaming analysis failed.");
      }
      if (event.event === "run_completed" && event.response) {
        finalResponse = event.response;
        handlers.onComplete?.(event.response);
      }
    }
    if (done) break;
  }

  if (buffer.trim()) {
    const event = parseSseBlock(buffer);
    if (event) {
      handlers.onEvent?.(event);
      if (event.event === "run_completed" && event.response) {
        finalResponse = event.response;
        handlers.onComplete?.(event.response);
      }
    }
  }
  if (!finalResponse) {
    throw new Error("Streaming analysis ended before the final response was received.");
  }
  return finalResponse;
}

function parseSseBlock(block: string): AnalysisStreamEvent | null {
  const lines = block.split("\n").map((line) => line.trim());
  const eventName = lines.find((line) => line.startsWith("event:"))?.replace(/^event:\s*/, "");
  const data = lines.find((line) => line.startsWith("data:"))?.replace(/^data:\s*/, "");
  if (!eventName || !data) return null;
  return { event: eventName, ...JSON.parse(data) } as AnalysisStreamEvent;
}
