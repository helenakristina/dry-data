import { useEffect, useState } from "react";
import { getGlobalTrend } from "@/api/client";
import { ChartRenderer } from "@/components/ChartRenderer";
import type { PlotlySpec } from "@/types/api";

export function StoryChart() {
  const [spec, setSpec] = useState<PlotlySpec | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getGlobalTrend()
      .then((data) => {
        if (!cancelled) setSpec(data);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (failed) {
    return (
      <p className="py-4 text-center text-sm text-gray-400">
        Chart unavailable — try refreshing.
      </p>
    );
  }

  if (!spec) {
    return (
      <p className="py-4 text-center text-sm text-gray-400">Loading chart…</p>
    );
  }

  return (
    <div>
      <div className="mb-3 px-1">
        <h2 className="text-lg font-semibold text-gray-800">
          Global alcohol consumption, 2000–2020
        </h2>
        <p className="text-sm text-gray-500">
          Average liters of pure alcohol consumed per person per year, across 200+ countries.
          WHO data published with a 2–3 year lag; dataset ends at 2020.
          Source: WHO via Our World in Data.
        </p>
      </div>
      <ChartRenderer spec={spec} />
    </div>
  );
}
