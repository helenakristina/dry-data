import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

  // CATCHES: toggle button is missing aria-expanded, or column details never appear
  it("toggles aria-expanded and shows column info when a dataset is clicked", async () => {
    const user = userEvent.setup();
    render(<DatasetBrowser />);

    // Wait for the dataset list to load
    const toggleButton = await screen.findByRole("button", {
      name: /fact_global_consumption/,
    });

    // Initially collapsed
    expect(toggleButton).toHaveAttribute("aria-expanded", "false");

    // Click to expand
    await user.click(toggleButton);

    // Now expanded
    expect(toggleButton).toHaveAttribute("aria-expanded", "true");

    // Column info is visible
    expect(screen.getByText("id")).toBeInTheDocument();
    expect(screen.getByText("liters_pure_alcohol_pc")).toBeInTheDocument();
  });
});
