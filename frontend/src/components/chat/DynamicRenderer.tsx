import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ListTree } from "lucide-react";
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
  ExecutiveSummary: {
    title: "Executive Summary",
    keys: ["executive_summary", "summary"],
  },
  EducationalExplainer: {
    title: "Explanation",
    keys: ["educational_explanation", "summary"],
  },
  Glossary: {
    title: "Glossary",
    keys: ["glossary", "terms"],
  },
  SectorTrends: {
    title: "Sector Trends",
    keys: ["market_overview", "trends", "news_summary"],
  },
  MacroDrivers: {
    title: "Macro Drivers",
    keys: ["macro_drivers", "market_overview"],
  },
  IndustryNews: {
    title: "Industry News",
    keys: ["news_summary", "news_highlights"],
  },
  TechnologyTrends: {
    title: "Technology Trends",
    keys: ["market_overview", "trends", "news_summary"],
  },
  Adoption: {
    title: "Adoption",
    keys: ["adoption", "market_overview", "trends"],
  },
  Research: {
    title: "Research",
    keys: ["research", "news_summary", "news_highlights"],
  },
  NewsTimeline: {
    title: "Latest News",
    keys: ["news_summary", "news_highlights"],
  },
  MovementDrivers: {
    title: "Movement Drivers",
    keys: ["movement_summary", "recent_catalysts"],
  },
  TechnicalCard: {
    title: "Technical Analysis",
    keys: ["technical_analysis", "technicals", "trend_analysis", "momentum"],
  },
  TechnicalMomentum: {
    title: "Technical Context",
    keys: ["technical_analysis", "technicals", "momentum"],
  },
  FundamentalCard: {
    title: "Fundamentals",
    keys: ["fundamentals", "company_overview"],
  },
  SentimentCard: {
    title: "Sentiment Analysis",
    keys: ["sentiment", "sentiment_analysis"],
  },
  SentimentMeter: {
    title: "Sentiment",
    keys: ["sentiment", "sentiment_analysis"],
  },
  ScenarioCards: {
    title: "Scenario Analysis",
    keys: ["scenario_analysis", "scenarios"],
  },
  ConfidenceGauge: {
    title: "Confidence",
    keys: ["confidence", "conviction"],
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
  BasicExplainer: {
    title: "Overview",
    keys: ["executive_summary", "summary", "educational_explanation"],
  },
  RelatedContent: {
    title: "Related",
    keys: ["related_content", "news_summary"],
  },
  DisclaimerWarning: {
    title: "Disclaimer",
    keys: ["disclaimer", "sebi_disclaimer"],
  },
  SafeRefusal: {
    title: "Notice",
    keys: ["executive_summary", "summary"],
  },
  EducationalRedirect: {
    title: "Learn More",
    keys: ["educational_explanation", "summary"],
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

  if (intent === "NEWS_ANALYSIS" || intent === "STOCK_MOVEMENT" || news || sentiment) {
    const parts = [
      news && `${news}`,
      sentiment && `Market sentiment: ${sentiment}`,
      movement && `Key driver: ${movement}`,
    ].filter(Boolean);

    if (parts.length) return parts.join("\n\n");
  }

  if (movement || technical) {
    const parts = [
      movement && `${movement}`,
      sentiment && `Sentiment: ${sentiment}`,
      technical && `Technical picture: ${technical}`,
    ].filter(Boolean);

    if (parts.length) return parts.join("\n\n");
  }

  for (const section of Object.values(result.sections || {})) {
    const text = stringifyValue(section?.synthesis).trim();
    if (text) return text;
  }

  return "I found the research context, but could not generate a complete response. Please try rephrasing your question with a specific company name or ticker.";
}

function normalizeForDuplicateCheck(text: string): string {
  return text.replace(/\s+/g, " ").trim().toLowerCase();
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
          if (normalizeForDuplicateCheck(text) === normalizeForDuplicateCheck(chatAnswer)) return null;

          return (
            <section key={block} className="rounded-xl border border-white/10 bg-white/[0.025] p-5">
              <h3 className="mb-3 flex items-center gap-2 text-base font-semibold uppercase tracking-wider text-zinc-400">
                <ListTree className="h-4 w-4 text-blue-300" aria-hidden="true" />
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
