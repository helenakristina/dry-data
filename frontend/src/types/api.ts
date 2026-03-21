/** Matches backend QueryRequest pydantic model. */
export interface QueryRequest {
  question: string;
}

/** Plotly figure spec returned by the LLM.
 *
 * The backend returns a complete Plotly figure object. The frontend
 * renders it as-is with react-plotly.js — no mapping layer needed.
 */
export interface PlotlySpec {
  data: Plotly.Data[];
  layout?: Partial<Plotly.Layout>;
}

/** Matches backend QueryResponse pydantic model. */
export interface QueryResponse {
  question: string;
  narrative: string;
  sql: string;
  chart: PlotlySpec | null;
  error: string | null;
}

/** Dataset metadata from GET /api/datasets. */
export interface DatasetInfo {
  table_name: string;
  description: string;
  row_count: number;
  columns: ColumnInfo[];
}

export interface ColumnInfo {
  name: string;
  type: string;
  nullable: boolean;
  sample_values: string[];
}

/** A single message in the chat history. */
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  chart: PlotlySpec | null;
  sql: string | null;
  timestamp: Date;
}
