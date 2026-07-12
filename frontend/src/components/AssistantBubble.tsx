import React from 'react';

interface AssistantBubbleProps {
  children: React.ReactNode;
}

const AssistantBubble: React.FC<AssistantBubbleProps> = ({ children }) => (
  <div className='flex mb-4'>
    <div className='bg-surface-container-low text-on-surface rounded-2xl px-4 py-2 max-w-[80%]'>
      {children}
    </div>
  </div>
);

export default AssistantBubble;
