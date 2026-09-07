export type CityJobCount = { city: string; job_count: number };
export type HealthResponse = { status: "ok" | "ready" };
export type StageStatus = {
  id: string;
  name: string;
  goal: string;
  acceptance: string;
  state: string;
};

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000"
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
};
