import { http, HttpResponse } from "msw";
import type { DatasetInfo, QueryResponse } from "../../types/api";

const mockDatasets: DatasetInfo[] = [
  {
    table_name: "fact_global_consumption",
    description: "Country-level WHO alcohol consumption data.",
    row_count: 100,
    columns: [
      { name: "id", type: "INTEGER", nullable: false, sample_values: [] },
      { name: "liters_pure_alcohol_pc", type: "FLOAT", nullable: true, sample_values: [] },
    ],
  },
  {
    table_name: "dim_country",
    description: "Countries with ISO codes.",
    row_count: 190,
    columns: [
      { name: "country_id", type: "INTEGER", nullable: false, sample_values: [] },
      { name: "country_name", type: "VARCHAR", nullable: false, sample_values: [] },
    ],
  },
];

const mockQueryResponse: QueryResponse = {
  question: "Which country has the highest consumption?",
  sql: "SELECT country_name, liters_pure_alcohol_pc FROM fact_global_consumption LIMIT 1",
  narrative: "France leads with 12.1 liters per capita.",
  chart: null,
  error: null,
};

const mockGlobalTrend = {
  data: [
    {
      type: "scatter",
      mode: "lines+markers",
      name: "Global average",
      x: [2019, 2020, 2021],
      y: [6.4, 6.2, 6.3],
    },
  ],
  layout: { title: "Global Alcohol Consumption" },
};

export const handlers = [
  http.get("/api/health", () => HttpResponse.json({ status: "ok" })),

  http.get("/api/datasets", () => HttpResponse.json(mockDatasets)),

  http.post("/api/query", () => HttpResponse.json(mockQueryResponse)),

  http.get("/api/story/global-trend", () => HttpResponse.json(mockGlobalTrend)),
];
