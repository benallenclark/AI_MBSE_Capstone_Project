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

export interface UploadResponse {
  job_id: string;
  model_id: string;
  status: string;
  sha256: string;
  links: {
    self: string;
    result: string;
  };
}

export interface JobStatus {
  job_id: string;
  model_id: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  progress: number;
  message?: string;
  timings?: Record<string, any>;
  links: {
    self: string;
    result: string;
  };
}

export interface AnalyzeResponse {
  schema_version: string;
  model: {
    vendor: string;
    version: string;
    model_id?: string;
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
 * Poll job status until completion
 */
async function pollJobStatus(jobId: string, onProgress?: (progress: number) => void): Promise<JobStatus> {
  const maxAttempts = 120; // 2 minutes with 1 second intervals
  let attempts = 0;

  while (attempts < maxAttempts) {
    try {
      const response = await axios.get<JobStatus>(`${API_BASE_URL}/v1/jobs/${jobId}`);
      const job = response.data;

      if (onProgress && job.progress) {
        onProgress(job.progress);
      }

      if (job.status === 'succeeded') {
        return job;
      }

      if (job.status === 'failed') {
        throw new Error(job.message || 'Analysis failed');
      }

      // Wait 1 second before next poll
      await new Promise(resolve => setTimeout(resolve, 1000));
      attempts++;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 404) {
        throw new Error('Job not found');
      }
      throw error;
    }
  }

  throw new Error('Analysis timeout - job did not complete in time');
}

/**
 * Backend response structure from /v1/models/{model_id}
 */
interface BackendModelResponse {
  schema_version: string;
  model_id: string;
  model: {
    vendor: string;
    version: string;
  };
  maturity_level: number;
  counts: {
    predicates_total: number;
    predicates_passed: number;
    predicates_failed: number;
    evidence_docs: number;
  };
  fingerprint: string;
  levels: Record<string, {
    num_predicates: {
      expected: number;
      present: number;
      passed: number;
      failed: number;
      missing: number;
    };
    predicates: Array<{
      id: string;
      passed: boolean;
      counts: Record<string, any>;
      source_tables?: string[];
    }>;
  }>;
}

/**
 * Transform backend response to frontend format
 */
function transformBackendResponse(backendData: BackendModelResponse): AnalyzeResponse {
  // Flatten all predicates from all levels into a single results array
  const results: AnalyzeResponse['results'] = [];

  Object.entries(backendData.levels || {}).forEach(([levelKey, levelData]) => {
    const mml = parseInt(levelKey, 10);
    levelData.predicates.forEach((predicate) => {
      results.push({
        id: predicate.id,
        mml: mml,
        passed: predicate.passed,
        details: predicate.counts || {},
        error: undefined,
      });
    });
  });

  return {
    schema_version: backendData.schema_version,
    model: {
      vendor: backendData.model.vendor,
      version: backendData.model.version,
      model_id: backendData.model_id,
    },
    maturity_level: backendData.maturity_level,
    summary: {
      total: backendData.counts.predicates_total,
      passed: backendData.counts.predicates_passed,
      failed: backendData.counts.predicates_failed,
    },
    results: results,
  };
}

/**
 * Get analysis results for a model
 */
async function getModelResults(modelId: string): Promise<AnalyzeResponse> {
  try {
    const response = await axios.get<BackendModelResponse>(`${API_BASE_URL}/v1/models/${modelId}`);

    // Transform backend response to frontend format
    return transformBackendResponse(response.data);
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const message = error.response?.data?.detail || error.message;
      throw new Error(`Failed to get results: ${message}`);
    }
    throw error;
  }
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
    // Step 1: Upload file
    const uploadResponse = await axios.post<UploadResponse>(
      `${API_BASE_URL}/v1/analyze/upload`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent: any) => {
          if (progressEvent.total && onProgress) {
            // Upload is 0-50% of total progress
            const uploadPercent = Math.round(
              (progressEvent.loaded * 50) / progressEvent.total
            );
            onProgress(uploadPercent);
          }
        },
      }
    );

    const { job_id, model_id } = uploadResponse.data;

    // Step 2: Poll for job completion
    await pollJobStatus(job_id, (jobProgress) => {
      if (onProgress) {
        // Job progress is 50-100% of total progress
        onProgress(50 + Math.round(jobProgress / 2));
      }
    });

    // Step 3: Get final results
    const results = await getModelResults(model_id);

    if (onProgress) {
      onProgress(100);
    }

    return results;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      const message = error.response?.data?.detail || error.message;
      throw new Error(`Upload failed: ${message}`);
    }
    throw error;
  }
};

