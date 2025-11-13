import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface ChatRequest {
  question: string;
  model_id: string;
  vendor: string;
  version: string;
}

export interface ChatResponse {
  answer: string;
  citations: Array<{
    doc_id: string;
    title: string;
  }>;
  retrieved: number;
  model_id: string;
  vendor: string;
  version: string;
  model: string;
  provider: string;
}

/**
 * Send a chat question to the RAG backend and get an AI-generated response
 * 
 * @param question - The user's question
 * @param model_id - The model ID from the analysis (e.g., "14b92d4a")
 * @param vendor - The vendor (e.g., "sparx")
 * @param version - The version (e.g., "17.1")
 * @returns Promise with the AI response and citations
 */
export async function sendChatMessage(
  question: string,
  model_id: string,
  vendor: string,
  version: string
): Promise<ChatResponse> {
  try {
    const response = await axios.post<ChatResponse>(
      `${API_BASE_URL}/v1/rag/ask`,
      {
        question,
        model_id,
        vendor,
        version,
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
        throw new Error('Invalid request. Please check your question and try again.');
      } else if (error.response?.status === 404) {
        throw new Error('RAG database not found for this model. The model may need to be reprocessed.');
      } else if (error.response?.status === 500) {
        throw new Error('Server error. Please try again later.');
      }
    }
    throw new Error('Failed to get AI response. Please try again.');
  }
}

/**
 * Stream chat responses using Server-Sent Events (SSE)
 * 
 * @param question - The user's question
 * @param model_id - The model ID from the analysis
 * @param vendor - The vendor
 * @param version - The version
 * @param onChunk - Callback for each text chunk received
 * @param onComplete - Callback when streaming is complete
 * @param onError - Callback for errors
 */
export async function streamChatMessage(
  question: string,
  model_id: string,
  vendor: string,
  version: string,
  onChunk: (chunk: string) => void,
  onComplete: () => void,
  onError: (error: Error) => void
): Promise<void> {
  try {
    const response = await fetch(`${API_BASE_URL}/v1/rag/ask_stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        question,
        model_id,
        vendor,
        version,
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    if (!reader) {
      throw new Error('Response body is not readable');
    }

    while (true) {
      const { done, value } = await reader.read();
      
      if (done) {
        onComplete();
        break;
      }

      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6); // Remove 'data: ' prefix
          try {
            const parsed = JSON.parse(data);
            if (parsed.delta) {
              onChunk(parsed.delta);
            }
          } catch (e) {
            // Ignore JSON parse errors for incomplete chunks
          }
        } else if (line.startsWith('event: done')) {
          onComplete();
          return;
        }
      }
    }
  } catch (error) {
    onError(error instanceof Error ? error : new Error('Unknown error occurred'));
  }
}

