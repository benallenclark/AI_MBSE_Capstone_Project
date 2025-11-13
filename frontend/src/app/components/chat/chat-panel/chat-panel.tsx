import { useState, useRef, useEffect } from 'react';
import { type AnalyzeResponse } from '../../../services/upload-service';
import { sendChatMessage } from '../../../services/chat-service';
import ChatMessage from '../chat-message/chat-message';
import { MdOutlineArrowCircleUp } from "react-icons/md";
import { RiRobot2Line } from "react-icons/ri";
import './chat-panel.css';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

interface ChatPanelProps {
  analysisData: AnalyzeResponse;
}

export default function ChatPanel({ analysisData }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when new messages arrive
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Send welcome message on mount
  useEffect(() => {
    const welcomeMessage: Message = {
      id: 'welcome',
      role: 'assistant',
      content: `Hi! I've analyzed your model. Here's a summary:

📊 **Maturity Level:** ${analysisData.maturity_level}/5
✅ **Tests Passed:** ${analysisData.summary.passed}/${analysisData.summary.total}
${analysisData.summary.failed > 0 ? `❌ **Tests Failed:** ${analysisData.summary.failed}` : ''}

What would you like to know about your analysis results?`,
      timestamp: new Date(),
    };
    setMessages([welcomeMessage]);
  }, [analysisData]);

  const suggestedQuestions = [
    'How can I improve my maturity score?',
    'Why did some tests fail?',
    'What do I need for the next maturity level?',
    'Explain the failed tests in detail',
  ];

  const handleSendMessage = async (content?: string) => {
    const messageContent = content || inputValue.trim();

    if (!messageContent || isLoading) return;

    // Add user message
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: messageContent,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    try {
      // Call the real RAG backend
      const response = await sendChatMessage(
        messageContent,
        analysisData.model?.model_id || 'unknown',
        analysisData.model?.vendor || 'sparx',
        analysisData.model?.version || '17.1'
      );

      const botMessage: Message = {
        id: `bot-${Date.now()}`,
        role: 'assistant',
        content: response.answer,
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, botMessage]);
    } catch (error) {
      // On error, show a helpful message
      const errorMessage: Message = {
        id: `bot-${Date.now()}`,
        role: 'assistant',
        content: `Sorry, I encountered an error: ${error instanceof Error ? error.message : 'Unknown error'}. Please try again.`,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const handleSuggestedQuestion = (question: string) => {
    handleSendMessage(question);
  };

  return (
    <div className="chat-panel">
      <div className="chat-header">
        <h2><RiRobot2Line /> AI Assistant</h2>
        <p className="chat-subtitle">Ask questions about your analysis results</p>
      </div>

      <div className="chat-messages">
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} />
        ))}
        
        {isLoading && (
          <div className="typing-indicator">
            <div className="typing-dot"></div>
            <div className="typing-dot"></div>
            <div className="typing-dot"></div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {messages.length === 1 && (
        <div className="suggested-questions">
          <p className="suggested-label">Suggested questions:</p>
          {suggestedQuestions.map((question, index) => (
            <button
              key={index}
              className="suggested-question-btn"
              onClick={() => handleSuggestedQuestion(question)}
              disabled={isLoading}
            >
              {question}
            </button>
          ))}
        </div>
      )}

      <div className="chat-input-container">
        <textarea
          ref={inputRef}
          className="chat-input"
          placeholder="Ask a question..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={isLoading}
          rows={1}
        />
        <button
          className="chat-send-btn"
          onClick={() => handleSendMessage()}
          disabled={!inputValue.trim() || isLoading}
          aria-label="Send message"
        >
          <MdOutlineArrowCircleUp />
        </button>
      </div>
    </div>
  );
}
