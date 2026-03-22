import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChartRenderer } from "./ChartRenderer";

// react-plotly.js renders a canvas which jsdom doesn't support.
// Mock it so we can test ChartRenderer's own logic.
vi.mock("react-plotly.js", () => ({
  default: () => <div data-testid="plotly-chart" />,
}));

const validSpec = {
  data: [{ type: "scatter" as const, x: [1, 2], y: [3, 4] }],
};

const emptySpec = { data: [] };

describe("ChartRenderer", () => {
  // CATCHES: ChartRenderer crashes or shows nothing when spec.data is empty
  it("renders no-data message when spec has no traces", () => {
    render(<ChartRenderer spec={emptySpec} />);
    expect(screen.getByText(/no data/i)).toBeInTheDocument();
  });

  // CATCHES: Chart is rendered without accessibility wrapper
  it("wraps chart in accessible container when data is present", () => {
    render(<ChartRenderer spec={validSpec} />);
    const wrapper = screen.getByRole("img");
    expect(wrapper).toBeInTheDocument();
  });

  // CATCHES: Plotly component is not rendered when data is present
  it("renders the Plotly chart when data is present", () => {
    render(<ChartRenderer spec={validSpec} />);
    expect(screen.getByTestId("plotly-chart")).toBeInTheDocument();
  });
});
