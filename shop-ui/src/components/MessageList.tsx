import { useEffect, useRef } from 'react';
import type { Message } from '../types';

interface MessageListProps {
  messages: Message[];
  isLoading: boolean;
}

export function MessageList({ messages, isLoading }: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  if (messages.length === 0) {
    return (
      <div className="message-list empty">
        <div className="welcome-message">
          <h2>Welcome to ShopChat</h2>
          <p>Ask me about products, orders, or customer information.</p>
          <div className="example-queries">
            <p><strong>Try asking:</strong></p>
            <ul>
              <li>"What products do you have in Footwear?"</li>
              <li>"Show me order ord_001"</li>
              <li>"What's the price of Nike Air Max?"</li>
            </ul>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="message-list">
      {messages.map((message) => (
        <div key={message.id} className={`message ${message.role}`}>
          <div className="message-header">
            <span className="message-role">
              {message.role === 'user' ? 'You' : 'Assistant'}
            </span>
            <span className="message-time">
              {message.timestamp.toLocaleTimeString()}
            </span>
          </div>
          <div className="message-content">
            {message.content || (isLoading && message.role === 'assistant' ? (
              <span className="typing-indicator">Thinking...</span>
            ) : null)}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
