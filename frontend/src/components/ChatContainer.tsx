import React from "react";
import UserBubble from "./UserBubble";
import AssistantBubble from "./AssistantBubble";

interface ChatContainerProps {
  query: string;
  response: React.ReactNode;
}

const ChatContainer: React.FC<ChatContainerProps> = ({ query, response }) => (
  <div className="space-y-4">
    <UserBubble message={query} />
    <AssistantBubble>{response}</AssistantBubble>
  </div>
);

export default ChatContainer;
