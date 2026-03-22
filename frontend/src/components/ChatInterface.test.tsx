import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChatInterface } from "./ChatInterface";

vi.mock("react-plotly.js", () => ({
  default: () => <div data-testid="plotly-chart" />,
}));

describe("ChatInterface", () => {
  // CATCHES: Landing page doesn't render StoryChart at all
  it("shows the global trend chart on the landing page", async () => {
    render(<ChatInterface />);
    await waitFor(() => {
      expect(screen.getByTestId("plotly-chart")).toBeInTheDocument();
    });
  });

  // CATCHES: Starter questions are missing or use wrong text
  it("shows WHO-related starter questions", () => {
    render(<ChatInterface />);
    expect(
      screen.getByText(/which countries drink the most/i),
    ).toBeInTheDocument();
  });
});
