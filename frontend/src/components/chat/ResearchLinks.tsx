import React from "react";
import { motion } from "framer-motion";

export interface SourceItem {
    title: string;
    url: string;
    source_type: string;
}

interface ResearchLinksProps {
    sources: SourceItem[];
}

const getSourceIcon = (sourceType: string): string => {
    const type = sourceType.toLowerCase();
    if (type.includes("yahoo")) return "📊";
    if (type.includes("reuters")) return "📰";
    if (type.includes("sec") || type.includes("filing")) return "📑";
    if (type.includes("annual")) return "📁";
    if (type.includes("earnings") || type.includes("transcript")) return "🎙️";
    return "🌍";
};

const ResearchLinks: React.FC<ResearchLinksProps> = ({ sources }) => {
    if (!sources || sources.length === 0) {
        return (
            <div className="text-zinc-500 text-sm font-medium py-4 px-2">
                No research links available for this query.
            </div>
        );
    }

    return (
        <div className="space-y-3 w-full">
            <h3 className="text-[10px] font-bold text-zinc-500 uppercase tracking-widest px-2 mb-1">
                Verified Sources
            </h3>
            <div className="flex flex-row lg:flex-col overflow-x-auto lg:overflow-x-visible gap-2.5 lg:space-y-2 pb-3 lg:pb-0 scrollbar-none w-full">
                {sources.map((src, idx) => (
                    <motion.a
                        key={`${src.url}-${idx}`}
                        href={src.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-3 px-3 py-2.5 rounded-xl border border-white/5 bg-zinc-900/40 hover:bg-zinc-800/80 hover:border-blue-500/30 text-zinc-300 hover:text-white transition-all duration-200 group shadow-md flex-shrink-0 w-[260px] lg:w-full"
                        whileHover={{ scale: 1.01 }}
                        whileTap={{ scale: 0.99 }}
                    >
                        <span className="text-base flex-shrink-0 bg-white/5 p-1 rounded-lg select-none">
                            {getSourceIcon(src.source_type)}
                        </span>
                        <div className="min-w-0 flex-1">
                            <p className="text-xs font-semibold truncate leading-tight">
                                {src.title}
                            </p>
                            <p className="text-[9px] text-zinc-400 uppercase tracking-wider font-semibold font-mono mt-0.5">
                                {src.source_type}
                            </p>
                        </div>
                        <span className="material-symbols-outlined text-zinc-500 group-hover:text-blue-400 text-xs transition-colors flex-shrink-0">
                            open_in_new
                        </span>
                    </motion.a>
                ))}
            </div>
        </div>
    );
};

export default ResearchLinks;
