import { useState, useEffect } from "react";
import { Database, Loader2, Table2 } from "lucide-react";
import { listDatasets } from "@/api/client";
import type { DatasetInfo } from "@/types/api";

export function DatasetBrowser() {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listDatasets()
      .then((data) => {
        if (!cancelled) setDatasets(data);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load datasets. Is the backend running?");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center px-6">
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-6 py-4 text-sm text-amber-800">
          {error}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4 overflow-y-auto px-6 py-6">
      <div className="flex items-center gap-2 text-gray-600">
        <Database className="h-5 w-5" />
        <h2 className="text-lg font-medium">
          {datasets.length} datasets available
        </h2>
      </div>

      {datasets.map((ds) => (
        <div
          key={ds.table_name}
          className="rounded-xl border border-gray-200 bg-white transition-shadow hover:shadow-sm"
        >
          <button
            onClick={() =>
              setExpanded(expanded === ds.table_name ? null : ds.table_name)
            }
            aria-expanded={expanded === ds.table_name}
            className="flex w-full items-center justify-between px-5 py-4 text-left"
          >
            <div>
              <div className="flex items-center gap-2">
                <Table2 className="h-4 w-4 text-brand-500" />
                <span className="font-mono text-sm font-medium text-gray-800">
                  {ds.table_name}
                </span>
                <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-500">
                  {ds.row_count.toLocaleString()} rows
                </span>
              </div>
              <p className="mt-1 text-sm text-gray-500">{ds.description}</p>
            </div>
          </button>

          {expanded === ds.table_name && (
            <div className="border-t border-gray-100 px-5 py-4">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-gray-400">
                    <th className="pb-2 font-medium">Column</th>
                    <th className="pb-2 font-medium">Type</th>
                    <th className="pb-2 font-medium">Sample values</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {ds.columns.map((col) => (
                    <tr key={col.name}>
                      <td className="py-2 font-mono text-xs text-gray-700">
                        {col.name}
                      </td>
                      <td className="py-2 text-xs text-gray-500">{col.type}</td>
                      <td className="py-2 text-xs text-gray-400">
                        {col.sample_values.join(", ")}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
