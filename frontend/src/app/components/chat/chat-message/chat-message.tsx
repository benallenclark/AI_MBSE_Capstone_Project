import type { JSX } from 'react';
import './chat-message.css';
import { RiRobot2Line } from "react-icons/ri";

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface ChatMessageProps {
  message: Message;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const formatTime = (date: Date): string => {
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  const formatContent = (content: string): JSX.Element[] => {
    // Simple markdown-like formatting
    const lines = content.split('\n');
    return lines.map((line, index) => {
      // Bold text: **text**
      let formattedLine = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      
      // Bullet points
      if (line.trim().startsWith('•') || line.trim().startsWith('-')) {
        return (
          <li key={index} dangerouslySetInnerHTML={{ __html: formattedLine.replace(/^[•-]\s*/, '') }} />
        );
      }
      
      // Numbered lists
      if (/^\d+\./.test(line.trim())) {
        return (
          <li key={index} dangerouslySetInnerHTML={{ __html: formattedLine.replace(/^\d+\.\s*/, '') }} />
        );
      }
      
      // Regular paragraphs
      if (line.trim()) {
        return (
          <p key={index} dangerouslySetInnerHTML={{ __html: formattedLine }} />
        );
      }
      
      return <br key={index} />;
    });
  };

  return (
    <div className={`chat-message chat-message-${message.role}`}>
      <div className="message-avatar">
        {message.role === 'assistant' ? <RiRobot2Line /> : '👤'}
      </div>
      <div className="message-content-wrapper">
        <div className="message-bubble">
          <div className="message-content">
            {formatContent(message.content)}
          </div>
        </div>
        <div className="message-timestamp">
          {formatTime(message.timestamp)}
        </div>
      </div>
    </div>
  );
}

