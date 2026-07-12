import React from "react";
import { motion } from "framer-motion";

type Props = {
  children: React.ReactNode;
};

export default function SentimentPanel({ children }: Props) {
  return (
    <motion.div
      whileHover={{ scale: 1.01, boxShadow: "0 0 10px rgba(66,133,244,0.4)" }}
      className="bg-gradient-to-b from-surface/30 to-surface/10 backdrop-blur-sm rounded-3xl border border-outline-variant/10 p-6 md:p-8"
    >
      {children}
    </motion.div>
  );
}
