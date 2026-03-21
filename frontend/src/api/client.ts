import type { QueryRequest, QueryResponse, DatasetInfo } from "@/types/api";

const BASE_URL = "/api";

class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const body = await res.text();
    throw new ApiError(res.status, body || res.statusText);
  }

  return res.json() as Promise<T>;
}

/** Send a natural language question and get a narrative + chart back. */
export async function queryData(question: string): Promise<QueryResponse> {
  const body: QueryRequest = { question };
  return request<QueryResponse>("/query", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Get the list of available datasets with metadata. */
export async function listDatasets(): Promise<DatasetInfo[]> {
  return request<DatasetInfo[]>("/datasets");
}

/** Healthcheck. */
export async function healthCheck(): Promise<{ status: string }> {
  return request<{ status: string }>("/health");
}
