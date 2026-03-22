import { describe, expect, it } from "vitest";
import { getGlobalTrend } from "./client";

describe("getGlobalTrend", () => {
  // CATCHES: getGlobalTrend function is missing from client.ts
  it("fetches /api/story/global-trend and returns a PlotlySpec", async () => {
    const spec = await getGlobalTrend();
    expect(spec).toBeDefined();
    expect(Array.isArray(spec.data)).toBe(true);
  });

  // CATCHES: data field is missing or not an array
  it("returns spec with at least one trace", async () => {
    const spec = await getGlobalTrend();
    expect(spec.data.length).toBeGreaterThan(0);
  });
});
