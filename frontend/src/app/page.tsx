"use client";

import { FormEvent, KeyboardEvent, useEffect, useRef, useState } from "react";
import Image from "next/image";
import { ArrowUp, BadgeCheck, Bot, Hourglass, Link, LoaderCircle } from "lucide-react";
import ResearchChat, { Message } from "../components/chat/ResearchChat";
import { SourceItem } from "../components/chat/DynamicRenderer";

interface ResearchEnvelope {
  summary?: string;
  ui_blocks?: string[];
  meta?: {
    conversation_id?: string | null;
    ticker?: string | null;
    generation_time_ms?: number;
  };
  intent?: {
    primary_intent?: string;
    intent_confidence?: number;
  };
  data?: Record<string, unknown>;
  warnings?: string[];
  sources?: SourceItem[];
}

const SUGGESTED_PROMPTS = [
  "Analyze TCS fundamentals",
  "Latest news on Reliance",
  "Why is Tesla falling today?",
  "Compare Infosys and TCS",
  "Explain PE ratio with example",
  "Indian IT sector outlook",
];

const CAPABILITIES = [
  "Stock research",
  "Latest market news",
  "Fundamental analysis",
  "Technical context",
  "Peer comparison",
  "Financial education",
];

export default function Home() {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [progressText, setProgressText] = useState("Reading your question...");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const latestSources =
    [...messages].reverse().find((message) => message.role === "assistant" && message.result?.sources?.length)
      ?.result?.sources || [];

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, isLoading]);

  useEffect(() => {
    if (!isLoading) return;

    const timers = [
      window.setTimeout(() => setProgressText("Finding market context..."), 1800),
      window.setTimeout(() => setProgressText("Checking news and signals..."), 4200),
      window.setTimeout(() => setProgressText("Preparing research answer..."), 7000),
    ];

    return () => timers.forEach(window.clearTimeout);
  }, [isLoading]);

  const submitQuery = async (prompt?: string) => {
    const nextQuery = (prompt ?? query).trim();
    if (!nextQuery || isLoading) return;

    setQuery("");
    setError(null);
    setProgressText("Reading your question...");
    setIsLoading(true);
    setMessages((current) => [...current, { role: "user", content: nextQuery }]);

    try {
      const response = await fetch("http://localhost:8001/api/v1/research/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: nextQuery,
          conversation_id: conversationId,
        }),
      });

      if (!response.ok) {
        const details = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(details?.detail || `Research engine error: ${response.status}`);
      }

      const data = (await response.json()) as ResearchEnvelope;
      setConversationId(data.meta?.conversation_id || conversationId);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: data.summary || "",
          result: data,
        },
      ]);
    } catch (err) {
      const message =
        err instanceof Error
          ? err.message
          : "Unable to connect to the research engine.";
      setError(message);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content:
            "I could not reach the research engine. Please make sure the backend is running, then try again.",
          result: {
            summary:
              "I could not reach the research engine. Please make sure the backend is running, then try again.",
            ui_blocks: ["ExecutiveSummary"],
          },
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    void submitQuery();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitQuery();
    }
  };

  return (
    <main className="sentinews-chatbot h-[100dvh] overflow-hidden bg-[#0f1218] text-zinc-100">
      <style
        dangerouslySetInnerHTML={{
          __html: `
            body > header, body > footer { display: none !important; }
            .sentinews-chatbot { font-size: 18px; }
            .sentinews-chatbot .text-xs { font-size: 0.95rem !important; line-height: 1.35rem !important; }
            .sentinews-chatbot .text-sm { font-size: 1.05rem !important; line-height: 1.55rem !important; }
            .sentinews-chatbot .text-base { font-size: 1.16rem !important; line-height: 1.75rem !important; }
            .sentinews-chatbot .text-lg { font-size: 1.28rem !important; line-height: 2rem !important; }
            .sentinews-chatbot .text-xl { font-size: 1.45rem !important; line-height: 2.15rem !important; }
            .sentinews-chatbot .text-2xl { font-size: 1.75rem !important; line-height: 2.35rem !important; }
            .sentinews-chatbot .text-3xl { font-size: 2rem !important; line-height: 2.55rem !important; }
            .sentinews-chatbot button,
            .sentinews-chatbot textarea,
            .sentinews-chatbot input { font-size: 1.18rem !important; }
            .sentinews-chatbot table { font-size: 1.08rem !important; }
            .sentinews-chatbot th,
            .sentinews-chatbot td { padding: 0.9rem 1rem !important; }
          `,
        }}
      />
      <div className="flex h-full min-h-0 flex-col lg:flex-row">
        <aside className="border-b border-white/10 bg-[#141821] px-7 py-7 lg:w-[390px] lg:border-b-0 lg:border-r xl:w-[430px]">
          <div className="flex items-center gap-4">
            <Image
              src="/sentinews-logo.jpg"
              alt="SentiNews AI"
              width={56}
              height={56}
              className="h-14 w-14 rounded-2xl object-cover shadow-lg shadow-blue-950/40"
            />
            <div>
              <h1 className="text-2xl font-semibold text-white">SentiNews AI</h1>
              <p className="text-sm text-zinc-400">Financial research chatbot</p>
            </div>
          </div>

          <div className="mt-8 rounded-2xl border border-white/10 bg-white/[0.03] p-6">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-semibold uppercase tracking-wider text-zinc-400">
                Status
              </span>
              <span className="flex items-center gap-2 text-sm text-emerald-300">
                <span className="h-2 w-2 rounded-full bg-emerald-400" />
                Ready
              </span>
            </div>
            <p className="mt-4 text-base leading-7 text-zinc-300">
              Ask about stocks, sectors, market news, ratios, or company comparisons.
            </p>
          </div>

          {latestSources.length === 0 && (
            <div className="mt-8">
              <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500">
                Try Asking
              </h2>
              <div className="mt-4 flex flex-col gap-3">
                {SUGGESTED_PROMPTS.map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => void submitQuery(prompt)}
                    disabled={isLoading}
                    className="rounded-xl border border-white/10 bg-white/[0.03] px-5 py-4 text-left text-base text-zinc-300 transition hover:border-blue-400/50 hover:bg-blue-500/10 hover:text-white disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className={`${latestSources.length > 0 ? "hidden" : "mt-8 hidden lg:block"}`}>
            <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500">
              Can Help With
            </h2>
            <div className="mt-4 flex flex-wrap gap-2.5">
              {CAPABILITIES.map((item) => (
                <span
                  key={item}
                  className="rounded-full border border-white/10 px-3 py-1.5 text-sm text-zinc-400"
                >
                  {item}
                </span>
              ))}
            </div>
          </div>

          <div className="mt-8">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-zinc-500">
              {latestSources.length > 0 ? "Source Links" : "References"}
            </h2>
            {latestSources.length > 0 ? (
              <div className="mt-4 flex max-h-[56dvh] flex-col gap-3 overflow-y-auto pr-1">
                {latestSources.slice(0, 12).map((source, index) => (
                  <a
                    key={`${source.title}-${index}`}
                    href={source.url || "#"}
                    target="_blank"
                    rel="noreferrer"
                    className="group rounded-xl border border-white/10 bg-white/[0.03] px-4 py-4 text-zinc-300 transition hover:border-blue-400/60 hover:bg-blue-500/10 hover:text-white"
                  >
                    <span className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-blue-300">
                      <Link className="h-4 w-4" aria-hidden="true" />
                      Source {index + 1}
                    </span>
                    <span className="block text-base font-medium leading-6 group-hover:underline">
                      {source.title || "Reference source"}
                    </span>
                    <span className="mt-2 block truncate text-sm text-zinc-500">
                      {source.source_type || "Source"}
                    </span>
                  </a>
                ))}
              </div>
            ) : (
              <div className="mt-4 rounded-xl border border-dashed border-white/10 bg-white/[0.02] px-4 py-5 text-base leading-7 text-zinc-500">
                Sources will appear here after a research response.
              </div>
            )}
          </div>
        </aside>

        <section className="flex min-h-0 flex-1 flex-col">
          <header className="z-20 border-b border-white/10 bg-[#0f1218]/90 px-10 py-5 backdrop-blur md:px-14">
            <div className="flex w-full items-center justify-between gap-4">
              <div>
                <p className="text-2xl font-medium text-white">AI Research Chat</p>
                <p className="text-base text-zinc-500">
                  {conversationId ? "Conversation memory active" : "Start a new market research chat"}
                </p>
              </div>
              <div className="hidden items-center gap-2 rounded-full border border-white/10 px-5 py-2.5 text-base text-zinc-400 sm:flex">
                <BadgeCheck className="h-5 w-5 text-blue-300" aria-hidden="true" />
                Educational research only
              </div>
            </div>
          </header>

          <div className="flex-1 overflow-y-auto px-10 py-9 md:px-14">
            <div className="w-full">
              {messages.length === 0 ? (
                <div className="flex min-h-[calc(100dvh-260px)] items-center justify-center pb-24">
                  <div className="max-w-3xl text-center">
                    <div className="mx-auto mb-6 flex h-20 w-20 items-center justify-center rounded-3xl border border-blue-400/30 bg-blue-500/15 text-blue-200">
                      <Bot className="h-11 w-11" aria-hidden="true" />
                    </div>
                    <h2 className="text-4xl font-semibold text-white">
                      Start a new financial research chat
                    </h2>
                    <p className="mt-4 text-xl leading-9 text-zinc-400">
                      Type your question below, or choose a prompt from the sidebar.
                    </p>
                  </div>
                </div>
              ) : (
                <ResearchChat messages={messages} />
              )}

              {isLoading && (
                <div className="mt-5 w-full rounded-2xl border border-white/10 bg-white/[0.03] p-5">
                  <div className="flex items-center gap-3 text-lg text-zinc-300">
                    <LoaderCircle className="h-6 w-6 animate-spin text-blue-300" aria-hidden="true" />
                    {progressText}
                  </div>
                </div>
              )}

              {error && (
                <div className="mt-5 w-full rounded-xl border border-red-500/30 bg-red-500/10 px-5 py-4 text-lg text-red-200">
                  {error}
                </div>
              )}

              <div ref={endRef} />
            </div>
          </div>

          <div className="border-t border-white/10 bg-[#0f1218]/95 px-10 py-7 backdrop-blur md:px-14">
            <form onSubmit={handleSubmit} className="w-full">
              <div className="flex items-end gap-5 rounded-3xl border border-white/10 bg-[#171b24] p-5 shadow-2xl shadow-black/20 focus-within:border-blue-400/70">
                <textarea
                  ref={inputRef}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={1}
                  disabled={isLoading}
                  placeholder="Ask about a stock, sector, news event, or financial concept..."
                  className="max-h-48 min-h-20 flex-1 resize-none bg-transparent px-5 py-5 text-2xl text-white outline-none placeholder:text-zinc-500 disabled:opacity-60"
                />
                <button
                  type="submit"
                  disabled={isLoading || !query.trim()}
                  className="flex h-20 w-20 shrink-0 items-center justify-center rounded-2xl bg-blue-600 text-white transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-zinc-700 disabled:text-zinc-400"
                  aria-label="Send message"
                >
                  {isLoading ? (
                    <Hourglass className="h-8 w-8" aria-hidden="true" />
                  ) : (
                    <ArrowUp className="h-8 w-8" aria-hidden="true" />
                  )}
                </button>
              </div>
              <p className="mt-3 text-center text-base text-zinc-500">
                AI output is for education and research, not financial advice.
              </p>
            </form>
          </div>
        </section>
      </div>
    </main>
  );
}
