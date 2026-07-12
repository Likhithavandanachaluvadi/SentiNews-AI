import React, { ReactNode } from 'react';
import { motion } from 'framer-motion';

interface ChatLayoutProps {
  children: ReactNode;
}

/**
 * ChatLayout – a reusable container that mimics a chat‑style conversation.
 * It applies a vertical stack with glass‑morphism styling and smooth entrance
 * animations. The component does **not** replace any existing UI; it can be
 * imported and used alongside the current report layout.
 */
const ChatLayout: React.FC<ChatLayoutProps> = ({ children }) => {
  return (
    <motion.div
      className="chat-layout max-w-4xl mx-auto p-4 space-y-6"
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
    >
      {children}
    </motion.div>
  );
};

export default ChatLayout;
