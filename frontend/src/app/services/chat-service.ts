import axios from 'axios';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

export interface ChatRequest {
  history: ChatMessage[];
}

export interface ChatResponse {
  role: string;
  content: string;
}

/**
 * Send a chat message with full conversation history to the MCP-powered backend
 *
 * @param history - The full conversation history including the new message
 * @returns Promise with the AI response
 */
export async function sendChatMessage(
  history: ChatMessage[]
): Promise<ChatResponse> {
  try {
    const response = await axios.post<ChatResponse>(
      `${API_BASE_URL}/api/chat`,
      {
        history,
      },
      {
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 400) {
        throw new Error(
          'Invalid request. Please check your question and try again.'
        );
      } else if (error.response?.status === 500) {
        throw new Error('Server error. Please try again later.');
      }
    }
    throw new Error('Failed to get AI response. Please try again.');
  }
}
