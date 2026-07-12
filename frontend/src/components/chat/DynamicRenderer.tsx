import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import AssistantMessage from "./AssistantMessage";

interface DynamicRendererProps {
  result?: ResearchResult;
}

export interface ResearchResult {
  summary?: string;
  ui_blocks?: string[];
  data?: Record<string, unknown>;
  sections?: Record<string, SectionPayload>;
  warnings?: string[];
  sources?: SourceItem[];
  intent?: {
    primary_intent?: string;
  };
}

interface SectionPayload {
  synthesis?: string;
  data?: Record<string, unknown>;
  status?: string;
}

export interface SourceItem {
  title?: string;
  url?: string;
  source_type?: string;
}

const TEXT_FIELDS: Record<string, { title: string; keys: string[] }> = {
  EducationalExplainer: {
    title: "Educational Explanation",
    keys: ["educational_explanation", "summary"],
  },
  NewsTimeline: {
    title: "Latest News",
    keys: ["news_summary", "news_highlights"],
  },
  MovementDrivers: {
    title: "Movement Drivers",
    keys: ["movement_summary", "recent_catalysts"],
  },
  TechnicalMomentum: {
    title: "Technical Context",
    keys: ["technical_analysis", "technicals", "momentum"],
  },
  FundamentalCard: {
    title: "Fundamentals",
    keys: ["fundamentals", "company_overview"],
  },
  RiskFactors: {
    title: "Risks",
    keys: ["risks", "weaknesses"],
  },
  ComparisonTable: {
    title: "Comparison",
    keys: ["comparison_summary", "comparison_table"],
  },
  Strengths: {
    title: "Strengths",
    keys: ["strengths"],
  },
  Weaknesses: {
    title: "Weaknesses",
    keys: ["weaknesses"],
  },
  SentimentPulse: {
    title: "Sentiment",
    keys: ["sentiment"],
  },
};

const markdownComponents = {
  h1: ({ ...props }) => <h1 className="mb-2 mt-4 text-2xl font-bold text-white" {...props} />,
  h2: ({ ...props }) => <h2 className="mb-2 mt-4 text-xl font-semibold text-white" {...props} />,
  h3: ({ ...props }) => <h3 className="mb-1 mt-3 text-lg font-medium text-white" {...props} />,
  p: ({ ...props }) => <p className="mb-3 leading-relaxed text-zinc-300" {...props} />,
  ul: ({ ...props }) => <ul className="mb-4 ml-4 list-disc space-y-1 text-zinc-300" {...props} />,
  ol: ({ ...props }) => <ol className="mb-4 ml-4 list-decimal space-y-1 text-zinc-300" {...props} />,
  li: ({ ...props }) => <li className="text-zinc-300" {...props} />,
  strong: ({ ...props }) => <strong className="font-semibold text-white" {...props} />,
  table: ({ ...props }) => (
    <div className="my-4 overflow-x-auto rounded-xl border border-white/10">
      <table className="w-full min-w-[520px] border-collapse text-left text-sm" {...props} />
    </div>
  ),
  thead: ({ ...props }) => <thead className="bg-white/10 text-white" {...props} />,
  th: ({ ...props }) => <th className="px-4 py-3 font-semibold" {...props} />,
  td: ({ ...props }) => <td className="border-t border-white/10 px-4 py-3 text-zinc-300" {...props} />,
};

function stringifyValue(value: unknown): string {
  if (!value) return "";
  if (typeof value === "string") return value.replace(/\\n/g, "\n");
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === "string") return `- ${item}`;
        if (item && typeof item === "object" && "title" in item) {
          return `- ${String((item as { title?: unknown }).title || "")}`;
        }
        return `- ${JSON.stringify(item)}`;
      })
      .join("\n");
  }
  if (typeof value === "object") return JSON.stringify(value, null, 2);
  return String(value);
}

function getDataText(result: ResearchResult, keys: string[]): string {
  for (const key of keys) {
    const value = result.data?.[key];
    const text = stringifyValue(value);
    if (text.trim()) return text;
  }

  for (const section of Object.values(result.sections || {})) {
    const text = stringifyValue(section?.synthesis);
    if (text.trim()) return text;
  }

  return "";
}

function getFirstDataText(result: ResearchResult, keys: string[]): string {
  for (const key of keys) {
    const text = stringifyValue(result.data?.[key]).trim();
    if (text) return text;
  }

  return "";
}

function buildConversationalAnswer(result: ResearchResult): string {
  const directSummary = stringifyValue(result.summary).trim();
  if (directSummary) return directSummary;

  const intent = result.intent?.primary_intent || "";
  const news = getFirstDataText(result, ["news_summary", "news_highlights"]);
  const movement = getFirstDataText(result, ["movement_summary", "recent_catalysts"]);
  const sentiment = getFirstDataText(result, ["sentiment"]);
  const technical = getFirstDataText(result, ["technical_analysis", "technicals", "momentum"]);
  const education = getFirstDataText(result, ["educational_explanation"]);
  const fundamentals = getFirstDataText(result, ["fundamentals", "company_overview"]);
  const comparison = getFirstDataText(result, ["comparison_summary"]);

  if (education) return education;
  if (comparison) return comparison;
  if (fundamentals) return fundamentals;

  if (intent === "NEWS_QA" || news || sentiment) {
    const parts = [
      news && `Here is the latest read: ${news}`,
      sentiment && `Market sentiment: ${sentiment}`,
      movement && `The main driver looks like: ${movement}`,
    ].filter(Boolean);

    if (parts.length) return parts.join("\n\n");
  }

  if (movement || technical) {
    const parts = [
      movement && `The stock seems to be moving because ${movement}`,
      sentiment && `Sentiment around it is ${sentiment}`,
      technical && `Technically, ${technical}`,
    ].filter(Boolean);

    if (parts.length) return parts.join("\n\n");
  }

  for (const section of Object.values(result.sections || {})) {
    const text = stringifyValue(section?.synthesis).trim();
    if (text) return text;
  }

  return "I found the research context, but I could not turn it into a clean response yet. Please try asking the same question with the company name or ticker.";
}

const DynamicRenderer: React.FC<DynamicRendererProps> = ({ result }) => {
  if (!result) return null;

  const uiBlocks = Array.isArray(result.ui_blocks) ? result.ui_blocks : [];
  const chatAnswer = buildConversationalAnswer(result);
  const visibleWarnings = (result.warnings || []).filter(
    (warning) => !warning.toLowerCase().includes("analysis skipped")
  );
  const customBlocks = uiBlocks.filter(
    (block) =>
      block !== "ExecutiveSummary" &&
      block !== "Citations" &&
      block !== "NewsTimeline" &&
      block !== "SentimentPulse"
  );

  return (
    <AssistantMessage>
      <div className="space-y-5">
        <div className="prose prose-invert max-w-none text-xl leading-9">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
            {chatAnswer}
          </ReactMarkdown>
        </div>

        {customBlocks.map((block) => {
          const config = TEXT_FIELDS[block];
          if (!config) return null;

          const text = getDataText(result, config.keys);
          if (!text.trim()) return null;

          return (
            <section key={block} className="rounded-xl border border-white/10 bg-white/[0.025] p-5">
              <h3 className="mb-3 flex items-center gap-2 text-base font-semibold uppercase tracking-wider text-zinc-400">
                <span className="material-symbols-outlined text-[18px] text-blue-300">
                  segment
                </span>
                {config.title}
              </h3>
              <div className="prose prose-invert max-w-none">
                <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>
                  {text}
                </ReactMarkdown>
              </div>
            </section>
          );
        })}

        {visibleWarnings.length > 0 && (
          <div className="rounded-xl border border-amber-400/20 bg-amber-400/10 px-4 py-3 text-sm text-amber-100">
            {visibleWarnings[0]}
          </div>
        )}
      </div>
    </AssistantMessage>
  );
};

export default DynamicRenderer;
