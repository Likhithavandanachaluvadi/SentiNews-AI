import React from 'react';

interface UserBubbleProps {
  message: string;
}

const UserBubble: React.FC<UserBubbleProps> = ({ message }) => (
  <div className='flex justify-end mb-4'>
    <div className='bg-google-blue text-white rounded-2xl px-4 py-2 max-w-[80%]'>
      {message}
    </div>
  </div>
);

export default UserBubble;
