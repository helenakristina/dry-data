import Plot from "react-plotly.js";
import type { PlotlySpec } from "@/types/api";

interface ChartRendererProps {
  spec: PlotlySpec;
}

/** Default layout overrides for a clean look inside the chat. */
const BASE_LAYOUT: Partial<Plotly.Layout> = {
  autosize: true,
  margin: { l: 50, r: 20, t: 40, b: 50 },
  font: { family: "Inter, system-ui, sans-serif", size: 13 },
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  xaxis: { gridcolor: "#e5e7eb" },
  yaxis: { gridcolor: "#e5e7eb" },
  colorway: [
    "#0c8de9", "#10b981", "#f59e0b", "#ef4444",
    "#8b5cf6", "#ec4899", "#06b6d4", "#84cc16",
  ],
};

/** Plotly toolbar — keep only the useful bits. */
const CONFIG: Partial<Plotly.Config> = {
  displayModeBar: true,
  modeBarButtonsToRemove: ["lasso2d", "select2d", "autoScale2d"],
  displaylogo: false,
  responsive: true,
};

export function ChartRenderer({ spec }: ChartRendererProps) {
  const mergedLayout: Partial<Plotly.Layout> = {
    ...BASE_LAYOUT,
    ...spec.layout,
  };

  return (
    <div className="rounded-xl border border-gray-100 bg-white p-2">
      <Plot
        data={spec.data}
        layout={mergedLayout}
        config={CONFIG}
        useResizeHandler
        className="w-full"
        style={{ width: "100%", height: "360px" }}
      />
    </div>
  );
}
