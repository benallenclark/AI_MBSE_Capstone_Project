import type { JSX } from 'react';
import './chat-message.css';
import { RiRobot2Line } from "react-icons/ri";
import { MdDownload } from "react-icons/md";

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
  const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

  const formatTime = (date: Date): string => {
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    });
  };

  // Extract download link and filename from message content
  // Still a work in progress (not 100% working yet)
  const extractDownloadLink = (content: string): { text: string; downloadUrl?: string; filename?: string } => {
    // Look for download URL pattern: Download URL: /api/reports/filename.pdf
    const urlMatch = content.match(/Download URL: (\/api\/reports\/[^\s]+\.pdf)/);
    const filenameMatch = content.match(/Filename: ([^\n]+)/);
    
    if (urlMatch) {
      return {
        text: content,
        downloadUrl: `${API_BASE_URL}${urlMatch[1]}`,
        filename: filenameMatch ? filenameMatch[1].trim() : 'report.pdf'
      };
    }
    
    return { text: content };
  };

  const formatContent = (content: string): JSX.Element[] => {
    const { text, downloadUrl, filename } = extractDownloadLink(content);
    
    // Simple markdown-like formatting
    const lines = text.split('\n');
    const elements: JSX.Element[] = [];
    
    lines.forEach((line, index) => {
      // Bold text: **text**
      const formattedLine = line.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
      
      // Bullet points
      if (line.trim().startsWith('•') || line.trim().startsWith('-')) {
        elements.push(
          <li key={index} dangerouslySetInnerHTML={{ __html: formattedLine.replace(/^[•-]\s*/, '') }} />
        );
      }
      // Numbered lists
      else if (/^\d+\./.test(line.trim())) {
        elements.push(
          <li key={index} dangerouslySetInnerHTML={{ __html: formattedLine.replace(/^\d+\.\s*/, '') }} />
        );
      }
      // Regular paragraphs
      else if (line.trim()) {
        elements.push(
          <p key={index} dangerouslySetInnerHTML={{ __html: formattedLine }} />
        );
      }
      else {
        elements.push(<br key={index} />);
      }
    });

    // Add download button if URL exists
    if (downloadUrl && filename) {
      elements.push(
        <div key="download-btn" className="download-button-container">
          <a 
            href={downloadUrl} 
            download={filename}
            className="download-button"
            target="_blank"
            rel="noopener noreferrer"
          >
            <MdDownload /> Download Report
          </a>
        </div>
      );
    }

    return elements;
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
