import { useState } from "react";
import { ChatInterface } from "@/components/ChatInterface";
import { DatasetBrowser } from "@/components/DatasetBrowser";
import { BarChart3, Database, MessageSquare } from "lucide-react";

type Tab = "chat" | "datasets";

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("chat");

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="border-b border-gray-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-5xl items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart3 className="h-7 w-7 text-brand-600" />
            <div>
              <h1 className="text-xl font-semibold tracking-tight">Dry Data</h1>
              <p className="text-sm text-gray-500">
                Explore alcohol trends through data
              </p>
            </div>
          </div>

          {/* Tab nav */}
          <nav className="flex gap-1 rounded-lg bg-gray-100 p-1">
            <button
              onClick={() => setActiveTab("chat")}
              className={`flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === "chat"
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-600 hover:text-gray-900"
              }`}
            >
              <MessageSquare className="h-4 w-4" />
              Ask questions
            </button>
            <button
              onClick={() => setActiveTab("datasets")}
              className={`flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === "datasets"
                  ? "bg-white text-gray-900 shadow-sm"
                  : "text-gray-600 hover:text-gray-900"
              }`}
            >
              <Database className="h-4 w-4" />
              Datasets
            </button>
          </nav>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-hidden">
        <div className="mx-auto h-full max-w-5xl">
          {activeTab === "chat" && <ChatInterface />}
          {activeTab === "datasets" && <DatasetBrowser />}
        </div>
      </main>
    </div>
  );
}
