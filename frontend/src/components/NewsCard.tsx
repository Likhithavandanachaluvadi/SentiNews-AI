import React from "react";
import { motion } from "framer-motion";

interface NewsItem {
  title: string;
  summary?: string;
  description?: string;
  source?: string;
  provider?: string;
  url?: string;
  publishedAt?: string; // ISO date string
  date?: string; // fallback string
  sentiment?: "positive" | "negative" | "neutral";
}

/**
 * Premium glass‑morphism news card.
 * Fixed height, responsive, hover elevation, and full‑card click.
 */
export default function NewsCard({ news }: { news: NewsItem }) {
  // Resolve display date
  const displayDate = news.publishedAt
    ? new Date(news.publishedAt).toLocaleString("en-IN", {
        day: "2-digit",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      })
    : news.date || "LAST 30D";

  const cleanedDesc = (news.summary || news.description || "")
    .replace(/<[^>]*>/g, "")
    .replace(/&nbsp;/gi, " ")
    .replace(/&amp;/g, "&")
    .replace(/&#39;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .trim()
    .slice(0, 150);

  const sentimentClass =
    news.sentiment === "positive"
      ? "border-success/20 hover:border-success/40 text-success bg-success/5"
      : news.sentiment === "negative"
      ? "border-danger/20 hover:border-danger/40 text-danger bg-danger/5"
      : "border-outline-variant/20 hover:border-outline-variant/40 text-on-surface-variant";

  return (
    <motion.article
      whileHover={{ scale: 1.02, boxShadow: "0 0 12px rgba(66,133,244,0.5)" }}
      className={`p-5 rounded-xl border ${sentimentClass} bg-gradient-to-b from-surface/30 to-surface/10 backdrop-blur-sm flex flex-col justify-between h-full cursor-pointer transition-shadow`}
      onClick={() => {
        if (news.url) window.open(news.url, "_blank", "noopener,noreferrer");
      }}
      tabIndex={0}
      role="button"
      aria-label={`Read article: ${news.title}`}
    >
      <div>
        <div className="flex justify-between items-center mb-2">
          <span className="text-[10px] font-mono text-on-surface-variant font-bold bg-surface-container-high px-2 py-0.5 rounded border border-outline-variant/10">
            {displayDate}
          </span>
          <span className={`text-[10px] font-mono font-extrabold uppercase px-2 py-0.5 rounded border ${sentimentClass}`}> 
            {news.sentiment || news.provider || news.source || "News"}
          </span>
        </div>
        <h4 className="text-lg font-bold text-on-surface leading-snug line-clamp-2 mb-2">
          {news.title}
        </h4>
      </div>
      <p className="text-xs text-on-surface-variant leading-relaxed mt-3 pt-2 border-t border-outline-variant/10 line-clamp-3">
        {cleanedDesc}
      </p>
      {news.source && (
        <p className="mt-2 text-[11px] text-google-blue font-semibold">
          Source: {news.source}
        </p>
      )}
      {news.url && (
        <a
          href={news.url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex items-center text-xs text-google-blue hover:underline"
          onClick={(e) => e.stopPropagation()}
        >
          Read Full Article
          <span className="material-symbols-outlined text-sm ml-1">open_in_new</span>
        </a>
      )}
    </motion.article>
  );
}
