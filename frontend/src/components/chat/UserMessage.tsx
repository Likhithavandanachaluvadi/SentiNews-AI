import React from "react";

interface UserMessageProps {
    query: string;
}

const UserMessage: React.FC<UserMessageProps> = ({ query }) => {
    return (
        <div className="flex justify-start">
            <div className="w-full rounded-2xl border border-white/10 bg-[#181d27] px-8 py-6 text-xl leading-9 text-white shadow-lg">
                {query}
            </div>
        </div>
    );
};

export default UserMessage;
