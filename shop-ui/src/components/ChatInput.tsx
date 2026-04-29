import { useState, type KeyboardEvent } from 'react';

interface ChatInputProps {
  onSend: (message: string) => void;
  onStop: () => void;
  isLoading: boolean;
  disabled?: boolean;
}

export function ChatInput({ onSend, onStop, isLoading, disabled }: ChatInputProps) {
  const [input, setInput] = useState('');

  const handleSubmit = () => {
    if (input.trim() && !isLoading) {
      onSend(input);
      setInput('');
    }
  };

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="chat-input">
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Type your message..."
        disabled={disabled || isLoading}
        rows={2}
      />
      <div className="chat-input-actions">
        {isLoading ? (
          <button onClick={onStop} className="stop-button">
            Stop
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={!input.trim() || disabled}
            className="send-button"
          >
            Send
          </button>
        )}
      </div>
    </div>
  );
}
