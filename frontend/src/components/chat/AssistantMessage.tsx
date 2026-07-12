import React from "react";

interface AssistantMessageProps {
  children: React.ReactNode;
}

const AssistantMessage: React.FC<AssistantMessageProps> = ({ children }) => {
  return (
    <div className="mb-3 flex w-full justify-start">
      <div className="w-full space-y-6 rounded-2xl border border-white/10 bg-transparent p-0">
        <div className="flex items-center gap-5">
          <div className="flex h-14 w-14 flex-shrink-0 select-none items-center justify-center rounded-xl bg-orange-500/90 text-2xl shadow-inner">
            <span className="material-symbols-outlined symbol-filled">smart_toy</span>
          </div>
          <div>
            <h2 className="text-2xl font-semibold leading-tight text-white">
              SentiNews AI
            </h2>
            <p className="text-base text-zinc-400">AI generated research</p>
          </div>
        </div>
        <div className="pl-20 text-xl leading-9 text-zinc-200">{children}</div>
      </div>
    </div>
  );
};

export default AssistantMessage;
