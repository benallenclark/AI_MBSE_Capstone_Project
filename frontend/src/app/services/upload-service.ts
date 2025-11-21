import axios from 'axios';

export const API_BASE_URL =
  (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000';

// Backend Analysis Report Types & API Functions
// --- 1. BACKEND TYPES (Raw response from /api/analysis/{id}) ---

export type RuleViolation = { id: string; message: string };

export type RuleResult = {
  id: string;
  rule_id?: string;
  status?: string;
  passed: boolean;
  violation_count?: number;
  violations?: RuleViolation[];
  description?: string;
  mml?: number;
  details?: any;
};

export type BackendAnalysisSummary = {
  schema_version: string;
  model: {
    vendor: string;
    version: string;
    model_id: string;
  };
  maturity_level: number;
  summary: {
    total: number;
    passed: number;
    failed: number;
  };
  results: RuleResult[];
};

// --- 2. FRONTEND TYPES (Adapted for UI consumption) ---

export interface AnalyzeResponse {
  schema_version: string;
  model: {
    vendor: string;
    version: string;
    model_id: string;
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
    details: {
      violation_count?: number;
      violations?: RuleViolation[];
      description?: string;
    };
    error?: string;
  }>;
}

// --- 3. API FUNCTIONS ---

/** Fetches the maturity report from the backend by session ID.
 * Returns null if the report is not found or still processing.
 */
export async function getMaturityReport(
  sessionId: string
): Promise<BackendAnalysisSummary | null> {
  const url = `${API_BASE_URL}/api/analysis/${encodeURIComponent(sessionId)}`;
  try {
    const { data } = await axios.get<BackendAnalysisSummary>(url);
    if (!data || typeof data !== 'object') return null;
    return data;
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.status === 404) {
      return null; // Analysis still processing or not found
    }
    throw err;
  }
}

/** Converts the backend analysis summary to the frontend AnalyzeResponse format */
export function toAnalyzeResponse(
  report: BackendAnalysisSummary
): AnalyzeResponse {
  const resultsList = Array.isArray(report.results) ? report.results : [];

  // Extract Session ID from the model object
  const sessionId = report.model?.model_id || 'unknown';
  const vendor = report.model?.vendor || 'unknown';
  const version = report.model?.version || 'unknown';

  return {
    schema_version: report.schema_version || '1',
    model: {
      vendor: vendor,
      version: version,
      model_id: sessionId,
    },
    maturity_level: report.maturity_level || 0,
    summary: report.summary || {
      total: resultsList.length,
      passed: resultsList.filter((r) => r.passed).length,
      failed: resultsList.filter((r) => !r.passed).length,
    },
    results: resultsList.map((r) => {
      const dets = r.details || {};

      return {
        id: r.id || r.rule_id || 'unknown',
        mml: r.mml || 0,
        passed: !!r.passed,
        details: {
          violation_count: dets.violation_count ?? r.violation_count,
          violations: dets.violations ?? r.violations,
          description: dets.description ?? r.description,
        },
      };
    }),
  };
}

// --- 4. UPLOAD & INGESTION FUNCTIONS ---

export interface UploadAndAnalyzeArgs {
  file: File;
  vendor: 'sparx' | 'cameo';
  version: string;
  modelId?: string;
  onProgress?: (progress: number) => void;
}

export interface UploadAndAnalyzeResult {
  sessionId: string;
}

/** Uploads the model file in batches and triggers analysis.
 * Calls onProgress callback with percentage (0-100) after each batch.
 */
export async function uploadAndAnalyze(
  args: UploadAndAnalyzeArgs
): Promise<UploadAndAnalyzeResult> {
  const { file, vendor, version, modelId, onProgress } = args;

  // 1) Read file and split into lines
  const fileText = await file.text();
  const lines = fileText.split('\n');

  // Define batch size (number of lines per batch)
  const BATCH_SIZE = 1000;

  // 2) Start ingest session
  const startResp = await axios.post(`${API_BASE_URL}/api/ingest/start`, {
    vendor,
    version,
    model_id: modelId ?? null,
    filename: file.name,
  });

  const sessionId: string =
    startResp.data?.session_id ?? startResp.data?.id ?? 'unknown';

  if (!sessionId || sessionId === 'unknown') {
    throw new Error(
      'Backend did not return a session id from /api/ingest/start'
    );
  }

  // 3) Upload lines in batches
  const totalBatches = Math.max(1, Math.ceil(lines.length / BATCH_SIZE));

  for (let batchIndex = 0; batchIndex < totalBatches; batchIndex++) {
    const start = batchIndex * BATCH_SIZE;
    const end = start + BATCH_SIZE;
    const batchLines = lines.slice(start, end);

    await axios.post(`${API_BASE_URL}/api/ingest/batch`, {
      session_id: sessionId,
      lines: batchLines,
    });

    if (onProgress) {
      const progress = Math.round(((batchIndex + 1) / totalBatches) * 100);
      onProgress(progress);
    }
  }

  // 4) Finish ingestion
  await axios.post(`${API_BASE_URL}/api/ingest/finish`, {
    session_id: sessionId,
  });

  return { sessionId };
}
