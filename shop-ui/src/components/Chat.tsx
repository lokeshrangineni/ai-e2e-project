import { useState } from 'react';
import { type UserContext, MOCK_USERS } from '../types';
import { useChat } from '../hooks/useChat';
import { RoleSelector } from './RoleSelector';
import { MessageList } from './MessageList';
import { ChatInput } from './ChatInput';

export function Chat() {
  const [userContext, setUserContext] = useState<UserContext>(MOCK_USERS.cust_001);

  const {
    messages,
    isLoading,
    error,
    sendMessage,
    stopGeneration,
    clearMessages,
  } = useChat({ userContext });

  const handleRoleChange = (newContext: UserContext) => {
    setUserContext(newContext);
    clearMessages();
  };

  return (
    <div className="chat-container">
      <header className="chat-header">
        <h1>ShopChat</h1>
        <RoleSelector
          userContext={userContext}
          onChange={handleRoleChange}
          disabled={isLoading}
        />
        <button
          onClick={clearMessages}
          disabled={isLoading || messages.length === 0}
          className="clear-button"
        >
          Clear
        </button>
      </header>

      {error && (
        <div className="error-banner">
          {error}
        </div>
      )}

      <MessageList messages={messages} isLoading={isLoading} />

      <ChatInput
        onSend={sendMessage}
        onStop={stopGeneration}
        isLoading={isLoading}
      />
    </div>
  );
}
