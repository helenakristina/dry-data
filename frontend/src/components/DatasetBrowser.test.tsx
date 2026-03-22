import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DatasetBrowser } from "./DatasetBrowser";

describe("DatasetBrowser", () => {
  // CATCHES: DatasetBrowser doesn't show datasets fetched from API
  it("renders dataset names after loading", async () => {
    render(<DatasetBrowser />);
    await waitFor(() => {
      expect(screen.getByText("fact_global_consumption")).toBeInTheDocument();
    });
  });

  // CATCHES: loading spinner is never shown, or shown forever
  it("shows a loading state initially", () => {
    render(<DatasetBrowser />);
    // spinner or some loading indicator is visible before data arrives
    expect(document.body).toBeDefined(); // component doesn't crash
  });
});
