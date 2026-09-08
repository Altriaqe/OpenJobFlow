export type CityJobCount = { city: string; job_count: number };
export type HealthResponse = { status: "ok" | "ready" };
export type StageStatus = {
  id: string;
  name: string;
  goal: string;
  acceptance: string;
  state: string;
};
export type CheckStatus = {
  name: string;
  status: string;
  summary: string;
  error: string | null;
};
export type OperationRun = {
  id: number;
  kind: string;
  report_date: string | null;
  status: string;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
};
export type DashboardSummary = {
  metrics: {
    job_count: number;
    city_count: number;
    batch_row_count: number | null;
    batch_status: string | null;
  };
  batch_finished_at: string | null;
  trend: Array<{ id: number; row_count: number; finished_at: string | null; status: string }>;
  stages: Array<{ id: string; name: string; state: string }>;
  checks: Array<{ name: string; status: string; summary: string }>;
  runs: Array<{ id: number; kind: string; status: string; started_at: string; finished_at: string | null }>;
  channels: Array<{ channel: string; status: string; updated_at: string }>;
  alerts: Array<{ level: string; title: string; detail: string }>;
  city_counts: CityJobCount[];
  delivery_totals: { successful: number; total: number };
};
export type DeliveryStatus = {
  channel: string;
  status: string;
  attempts: number;
  updated_at: string;
};

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ??
  (import.meta.env.DEV ? "http://127.0.0.1:8000" : "/api")
).replace(/\/$/, "");

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) throw new Error(`JobFlow API ${response.status}`);
  return response.json() as Promise<T>;
}

export const jobflowApi = {
  health: () => get<HealthResponse>("/health"),
  readiness: () => get<HealthResponse>("/ready"),
  cityJobCounts: (limit = 20) =>
    get<CityJobCount[]>(`/analytics/cities?limit=${limit}`),
  stageStatuses: () => get<StageStatus[]>("/operations/stages"),
  recentChecks: () => get<CheckStatus[]>("/operations/checks"),
  recentRuns: () => get<OperationRun[]>("/operations/runs"),
  dashboardSummary: () => get<DashboardSummary>("/dashboard/summary"),
  deliveryStatuses: (date: string) => get<DeliveryStatus[]>(`/dashboard/deliveries?snapshot_date=${date}`),
};
