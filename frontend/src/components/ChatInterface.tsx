import { useState, useRef, useEffect } from "react";
import { Send, Loader2, ChevronDown } from "lucide-react";
import { queryData } from "@/api/client";
import { ChartRenderer } from "@/components/ChartRenderer";
import { StoryChart } from "@/components/StoryChart";
import type { ChatMessage } from "@/types/api";

const STARTER_QUESTIONS = [
  "Which countries drink the most alcohol per capita?",
  "How has 'sober curious' trended on Google over the past 5 years?",
  "What percentage of US adults binge drink, by state?",
  "How much does the average American household spend on alcohol per year?",
];

export function ChatInterface() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSubmit(question?: string) {
    const q = question ?? input.trim();
    if (!q || isLoading) return;

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: q,
      chart: null,
      sql: null,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await queryData(q);
      const assistantMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: response.narrative,
        chart: response.chart,
        sql: response.sql,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch {
      const errorMsg: ChatMessage = {
        id: crypto.randomUUID(),
        role: "assistant",
        content:
          "Sorry, I had trouble answering that question. The backend might not be running yet, or the data pipeline hasn't been loaded.",
        chart: null,
        sql: null,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {messages.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-8">
            <div className="w-full max-w-3xl">
              <StoryChart />
            </div>
            <div className="text-center">
              <h2 className="mb-2 text-2xl font-semibold text-gray-800">
                What do you want to explore?
              </h2>
              <p className="mb-6 max-w-md text-center text-gray-500">
                Ask questions about global alcohol trends, US drinking patterns,
                spending data, or the sober-curious movement.
              </p>
            </div>
            <div className="grid max-w-2xl grid-cols-2 gap-3">
              {STARTER_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => handleSubmit(q)}
                  className="rounded-xl border border-gray-200 bg-white px-4 py-3 text-left text-sm text-gray-700 transition-all hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-2xl rounded-2xl px-5 py-3 ${
                    msg.role === "user"
                      ? "bg-brand-600 text-white"
                      : "bg-white border border-gray-200 text-gray-800"
                  }`}
                >
                  <p className="whitespace-pre-wrap leading-relaxed">
                    {msg.content}
                  </p>

                  {msg.chart && (
                    <div className="mt-4">
                      <ChartRenderer spec={msg.chart} />
                    </div>
                  )}

                  {msg.sql && (
                    <details className="mt-3">
                      <summary className="cursor-pointer text-xs text-gray-400 hover:text-gray-600">
                        <ChevronDown className="mr-1 inline h-3 w-3" />
                        View SQL
                      </summary>
                      <pre className="mt-2 overflow-x-auto rounded-lg bg-gray-50 p-3 font-mono text-xs text-gray-600">
                        {msg.sql}
                      </pre>
                    </details>
                  )}
                </div>
              </div>
            ))}

            {isLoading && (
              <div className="flex justify-start">
                <div className="flex items-center gap-2 rounded-2xl border border-gray-200 bg-white px-5 py-3 text-gray-500">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Querying the data...
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="border-t border-gray-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-3xl items-center gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
            placeholder="Ask a question about alcohol trends..."
            disabled={isLoading}
            className="flex-1 rounded-xl border border-gray-300 px-4 py-3 text-sm transition-colors placeholder:text-gray-400 focus:border-brand-400 focus:outline-none focus:ring-2 focus:ring-brand-100 disabled:opacity-50"
          />
          <button
            onClick={() => handleSubmit()}
            disabled={!input.trim() || isLoading}
            className="rounded-xl bg-brand-600 p-3 text-white transition-colors hover:bg-brand-700 disabled:opacity-40"
          >
            <Send className="h-5 w-5" />
          </button>
        </div>
      </div>
    </div>
  );
}
