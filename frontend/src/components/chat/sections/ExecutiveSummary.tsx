import React from "react";
import ReactMarkdown from "react-markdown";
import type { Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { BarChart3, ExternalLink } from "lucide-react";

interface ExecutiveSummaryProps {
    result: Record<string, unknown>;
}

const ExecutiveSummary: React.FC<ExecutiveSummaryProps> = ({ result }) => {
    const data = (result?.data && typeof result.data === "object" ? result.data : {}) as Record<string, unknown>;
    const meta = (result?.meta && typeof result.meta === "object" ? result.meta : {}) as Record<string, unknown>;
    const sections = (result?.sections && typeof result.sections === "object" ? result.sections : {}) as Record<string, unknown>;
    const fundamentalsSection = (
        sections.fundamentals && typeof sections.fundamentals === "object"
            ? sections.fundamentals
            : {}
    ) as Record<string, unknown>;
    const fundamentalsData = (
        fundamentalsSection.data && typeof fundamentalsSection.data === "object"
            ? fundamentalsSection.data
            : {}
    ) as Record<string, unknown>;
    const [nowMs] = React.useState(() => Date.now());

    const summary =
        result?.executive_summary ||
        result?.summary ||
        result?.report ||
        data.executive_summary ||
        data.summary ||
        data.report ||
        fundamentalsData.summary ||
        "";

    const ticker = String(result?.ticker || meta.ticker || "NIFTY");

    if (!String(summary).trim()) {
        return null;
    }

    const cleanText = (raw: string): string => {
        if (!raw) return "";
        return raw.replace(/\\n/g, "\n");
    };

    const getMetricVal = (m: unknown): unknown => {
        if (m === null || m === undefined) return "";
        if (typeof m === 'object') {
            const metric = m as Record<string, unknown>;
            if (metric.display_value) {
                return metric.display_value;
            }
            if ('value' in metric) {
                return metric.value;
            }
        }
        return m;
    };

    const getFreshnessBadge = (timestamp: string | null): { label: string; color: string } => {
        if (!timestamp || timestamp === "N/A") return { label: "STALE", color: "bg-red-500/10 text-red-400 border-red-500/20" };
        try {
            const diffMs = nowMs - new Date(timestamp).getTime();
            const diffMins = diffMs / 1000 / 60;
            if (diffMins < 15) return { label: "LIVE", color: "bg-green-500/15 text-green-400 border-green-500/30 font-bold" };
            if (diffMins < 1440) return { label: "RECENT", color: "bg-blue-500/15 text-blue-400 border-blue-500/30 font-bold" };
            return { label: "STALE", color: "bg-red-500/10 text-red-400 border-red-500/20" };
        } catch {
            return { label: "STALE", color: "bg-red-500/10 text-red-400 border-red-500/20" };
        }
    };

    const getSourceLink = (metricObj: unknown, defaultSource: string, tickerStr: string): string | null => {
        const metric = metricObj && typeof metricObj === 'object' ? metricObj as Record<string, unknown> : {};
        if (typeof metric.source_url === "string" && metric.source_url) {
            return metric.source_url;
        }
        const source = String(metric.source || defaultSource);
        if (!source || source === "N/A") return null;
        
        const cleanTicker = tickerStr.split(".")[0].toUpperCase();
        if (source.toLowerCase().includes("yfinance")) return `https://finance.yahoo.com/quote/${cleanTicker}`;
        if (source.toLowerCase().includes("screener")) return `https://www.screener.in/company/${cleanTicker}/consolidated/`;
        if (source.toLowerCase().includes("technical")) return `https://www.tradingview.com/symbols/${cleanTicker}`;
        return null;
    };

    const getMissingReason = (name: string, metricObj: unknown): string => {
        const metric = metricObj && typeof metricObj === 'object' ? metricObj as Record<string, unknown> : {};
        if (typeof metric.reason === "string" && metric.reason) {
            return metric.reason;
        }
        const lowercaseName = name.toLowerCase();
        if (lowercaseName.includes("peg") || lowercaseName.includes("pe ratio") || lowercaseName.includes("debt/equity")) {
            return "Not applicable";
        }
        return "Not reported";
    };

    const compactMetrics = [
        { label: "Current Price", key: "Current Price" },
        { label: "Market Cap", key: "Market Cap" },
        { label: "PE Ratio", key: "P/E Ratio (TTM)" },
        { label: "Dividend Yield", key: "Dividend Yield" },
    ];

    const keyStatistics = (
        data.key_statistics && typeof data.key_statistics === "object"
            ? data.key_statistics
            : {}
    ) as Record<string, unknown>;

    const markdownComponents: Components = {
        h1: ({ node: _node, ...props }) => <h1 className="text-3xl font-bold text-white mt-5 mb-3" {...props} />,
        h2: ({ node: _node, ...props }) => <h2 className="text-2xl font-semibold text-white mt-5 mb-3" {...props} />,
        h3: ({ node: _node, ...props }) => <h3 className="text-xl font-medium text-white mt-4 mb-2" {...props} />,
        p: ({ node: _node, ...props }) => <p className="text-lg text-zinc-300 leading-8 mb-4" {...props} />,
        ul: ({ node: _node, ...props }) => <ul className="list-disc list-inside text-lg text-zinc-300 space-y-2 ml-4 mb-5" {...props} />,
        ol: ({ node: _node, ...props }) => <ol className="list-decimal list-inside text-lg text-zinc-300 space-y-2 ml-4 mb-5" {...props} />,
        li: ({ node: _node, ...props }) => <li className="text-lg text-zinc-300 mb-1.5" {...props} />,
        strong: ({ node: _node, ...props }) => <strong className="font-semibold text-white" {...props} />,
        em: ({ node: _node, ...props }) => <em className="italic text-zinc-300" {...props} />,
        code: ({ node: _node, className, children, ...props }) => {
            const isInline = !className;
            return isInline ? (
                <code className="bg-zinc-800 text-zinc-200 px-1.5 py-0.5 rounded font-mono text-sm" {...props}>
                    {children}
                </code>
            ) : (
                <pre className="bg-zinc-800 text-zinc-200 p-4 rounded-lg overflow-x-auto font-mono text-sm my-3 border border-white/5">
                    <code className={className} {...props}>
                        {children}
                    </code>
                </pre>
            );
        },
        table: ({ node: _node, ...props }) => <table className="w-full text-left border-collapse my-5 border border-zinc-700/50 text-lg" {...props} />,
        thead: ({ node: _node, ...props }) => <thead className="bg-zinc-800/80 text-white font-semibold text-base border-b border-zinc-700" {...props} />,
        tbody: ({ node: _node, ...props }) => <tbody className="divide-y divide-zinc-800 text-base text-zinc-300" {...props} />,
        tr: ({ node: _node, ...props }) => <tr className="hover:bg-zinc-800/30 transition-colors" {...props} />,
        th: ({ node: _node, ...props }) => <th className="px-4 py-2.5 font-semibold" {...props} />,
        td: ({ node: _node, ...props }) => <td className="px-4 py-2.5" {...props} />,
    };

    return (
        <div className="space-y-4">
            <h3 className="text-lg font-semibold text-zinc-400 tracking-wider uppercase mb-3">
                Executive Summary
            </h3>
            <div className="prose prose-invert max-w-none text-lg text-zinc-300 prose-p:my-3 prose-p:text-lg prose-p:leading-8 prose-headings:mt-5 prose-headings:mb-3 prose-ul:my-3 prose-ol:my-3 prose-li:my-1 prose-li:text-lg prose-pre:my-4">
                <ReactMarkdown
                    remarkPlugins={[remarkGfm]}
                    components={markdownComponents}
                >
                    {cleanText(String(summary))}
                </ReactMarkdown>
            </div>

            {Object.keys(keyStatistics).length > 0 && (
                <div className="mt-5 border-t border-zinc-800 pt-5">
                    <h4 className="text-xs font-mono uppercase tracking-widest font-extrabold text-zinc-400 mb-3 flex items-center gap-2">
                        <BarChart3 className="h-4 w-4 text-blue-400" aria-hidden="true" />
                        Key Statistics Preview
                    </h4>
                    <div className="grid grid-cols-2 gap-3">
                        {compactMetrics.map((m, idx) => {
                            const metricData = keyStatistics[m.key] as Record<string, unknown> | undefined;
                            const rawVal = getMetricVal(metricData);
                            const hasVal = rawVal !== null && rawVal !== undefined && rawVal !== "" && rawVal !== "N/A" && rawVal !== "Unavailable";
                            const val = hasVal ? String(rawVal) : "Unavailable";
                            const reason = hasVal ? "" : getMissingReason(m.label, metricData);
                            const src = String(metricData?.source || "N/A");
                            const timestamp = typeof metricData?.timestamp === "string" ? metricData.timestamp : "";
                            const time = timestamp && timestamp !== "N/A" ? new Date(timestamp).toLocaleDateString("en-IN", { hour: "2-digit", minute: "2-digit" }) : "N/A";
                            const conf = metricData?.confidence !== undefined ? String(metricData.confidence) : "N/A";
                            const badge = getFreshnessBadge(timestamp || null);
                            const sourceLink = getSourceLink(metricData, src, ticker);

                            return (
                                <div
                                    key={idx}
                                    className="p-3 bg-zinc-900/60 rounded-xl border border-zinc-800/80 hover:border-zinc-700/40 transition-all flex flex-col justify-between"
                                >
                                    <div>
                                        <div className="flex justify-between items-start gap-2 mb-1">
                                            <span className="text-[9px] text-zinc-500 font-mono uppercase tracking-wider truncate">
                                                {m.label}
                                            </span>
                                            <span className={`text-[7px] font-mono border px-1.5 py-0.2 rounded uppercase tracking-wider ${badge.color}`}>
                                                {badge.label}
                                            </span>
                                        </div>
                                        <span className={`text-sm font-bold font-mono tracking-tight ${hasVal ? "text-white" : "text-zinc-500"}`}>
                                            {val}
                                        </span>
                                        {!hasVal && (
                                            <span className="block text-[8px] font-mono text-red-400 mt-0.5">
                                                Reason: {reason}
                                            </span>
                                        )}
                                    </div>
                                    <div className="mt-3 pt-1.5 border-t border-zinc-800/60 flex flex-col gap-0.5 text-[8px] font-mono text-zinc-500">
                                        <div className="flex justify-between items-center gap-1">
                                            <span>Source:</span>
                                            <span className="text-zinc-300 font-semibold truncate flex items-center gap-1">
                                                {src}
                                                {sourceLink && (
                                                    <a href={sourceLink} target="_blank" rel="noopener noreferrer" className="hover:text-blue-400 cursor-pointer inline-flex items-center">
                                                        <ExternalLink className="h-3 w-3" aria-hidden="true" />
                                                    </a>
                                                )}
                                            </span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span>Confidence:</span>
                                            <span className={`font-semibold ${conf === "High" || conf === "0.9" || conf === "1.0" ? "text-green-400" : conf === "Moderate" ? "text-yellow-400" : "text-zinc-300"}`}>{conf}</span>
                                        </div>
                                        <div className="flex justify-between">
                                            <span>Updated:</span>
                                            <span className="text-zinc-400 truncate max-w-[60px]">{time}</span>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}
        </div>
    );
};

export default ExecutiveSummary;
