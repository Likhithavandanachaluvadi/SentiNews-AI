import React from "react";
import NewsCard from "@/components/NewsCard";
import { motion, AnimatePresence } from "framer-motion";

type NewsItem = {
  title: string;
  summary?: string;
  description?: string;
  source?: string;
  provider?: string;
  url?: string;
  publishedAt?: string;
  date?: string;
  sentiment?: "positive" | "negative" | "neutral";
  category?: string;
  imageUrl?: string;
};

interface NewsGridProps {
  newsItems: NewsItem[];
}

export default function NewsGrid({ newsItems }: NewsGridProps) {
  return (
    <motion.div layout className="flex flex-col space-y-6">
      <AnimatePresence>
        {newsItems.map((news, idx) => (
          <NewsCard key={idx} news={news} />
        ))}
      </AnimatePresence>
    </motion.div>
  );
}
