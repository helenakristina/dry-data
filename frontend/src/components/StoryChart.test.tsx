import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { server } from "../test/mocks/server";
import { StoryChart } from "./StoryChart";

// react-plotly.js renders a canvas which jsdom doesn't support.
vi.mock("react-plotly.js", () => ({
  default: () => <div data-testid="plotly-chart" />,
}));

describe("StoryChart", () => {
  // CATCHES: API failure leaves loading state shown forever
  it("shows error message when API returns 500", async () => {
    server.use(
      http.get("/api/story/global-trend", () =>
        HttpResponse.json({ detail: "Internal Server Error" }, { status: 500 }),
      ),
    );

    render(<StoryChart />);

    await waitFor(() => {
      expect(
        screen.getByText("Chart unavailable — try refreshing."),
      ).toBeInTheDocument();
    });

    expect(screen.queryByText("Loading chart…")).not.toBeInTheDocument();
  });

  // CATCHES: successful load shows the chart heading, not the fallback
  it("shows the chart heading after successful load", async () => {
    render(<StoryChart />);

    await waitFor(() => {
      expect(
        screen.getByText("Global alcohol consumption, 2000–2020"),
      ).toBeInTheDocument();
    });

    expect(screen.queryByText("Loading chart…")).not.toBeInTheDocument();
    expect(
      screen.queryByText("Chart unavailable — try refreshing."),
    ).not.toBeInTheDocument();
  });
});
