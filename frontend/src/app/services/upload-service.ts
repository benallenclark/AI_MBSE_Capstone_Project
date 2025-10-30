import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface UploadProgressCallback {
  (progress: number): void;
}

export interface AnalyzeUploadParams {
  file: File;
  vendor: 'sparx' | 'cameo';
  version: string;
  modelId?: string;
  onProgress?: UploadProgressCallback;
}

export interface AnalyzeResponse {
  schema_version: string;
  model: {
    vendor: string;
    version: string;
  };
  maturity_level: number;
  summary: {
    total: number;
    passed: number;
    failed: number;
  };
  results: Array<{
    id: string;
    mml: number;
    passed: boolean;
    details: Record<string, any>;
    error?: string;
  }>;
}

/**
 * Upload and analyze a model file with progress tracking
 * 
 * @param params - Upload parameters including file, vendor, version, and progress callback
 * @returns Promise resolving to the analysis response
 * @throws Error if upload fails
 */
export const uploadAndAnalyze = async ({
  file,
  vendor,
  version,
  modelId,
  onProgress,
}: AnalyzeUploadParams): Promise<AnalyzeResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('vendor', vendor);
  formData.append('version', version);
  
  if (modelId) {
    formData.append('model_id', modelId);
  }

  try {
    const response = await axios.post<AnalyzeResponse>(
      `${API_BASE_URL}/v1/analyze/upload`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent: any) => {
          if (progressEvent.total && onProgress) {
            const percentComplete = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
            onProgress(percentComplete);
          }
        },
      }
    );

    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const message = error.response?.data?.detail || error.message;
      throw new Error(`Upload failed: ${message}`);
    }
    throw error;
  }
};

