import React from "react";
import UserMessage from "./UserMessage";
import DynamicRenderer, { ResearchResult } from "./DynamicRenderer";

export interface Message {
    role: "user" | "assistant";
    content: string;
    result?: ResearchResult;
}

interface ResearchChatProps {
    messages: Message[];
}

const ResearchChat: React.FC<ResearchChatProps> = ({ messages }) => {
    return (
        <div className="w-full space-y-10 px-0 pb-28 pt-3">
            {messages.map((msg, idx) => (
                <div key={idx} className="w-full">
                    {msg.role === "user" ? (
                        <UserMessage query={msg.content} />
                    ) : (
                        <DynamicRenderer result={msg.result} />
                    )}
                </div>
            ))}
        </div>
    );
};

export default ResearchChat;
