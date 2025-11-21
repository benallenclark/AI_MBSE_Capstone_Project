import { useState } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import FileDrop from '../shared/file-drop/file-drop';
import UploadItemStatus, { type UploadStatus } from './components/upload-item-status/upload-item-status';
import './upload-wizard.css';

// --- CONFIGURATION ---
const API_BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000';
const BATCH_SIZE = 1000;

interface ModelFile {
  file: File;
  vendor: 'sparx' | 'cameo';
  version: string;
  modelId?: string;
}

interface UploadWizardProps {
  onAnalysisFinished?: (sessionId: string) => void;
}

export default function UploadWizard({ onAnalysisFinished }: UploadWizardProps) {
  const navigate = useNavigate();

 // --- STATE ---
  const [selectedFile, setSelectedFile] = useState<ModelFile | null>(null);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('pending');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState<string | undefined>();

  // --- Handlers ---
  const handleFilesSelected = (files: File[]) => {
    if (files.length > 0) {
      setSelectedFile({
        file: files[0],
        vendor: 'sparx',
        version: '',
        modelId: ''
      });
      setUploadStatus('pending');
      setUploadProgress(0);
      setUploadError(undefined);
    }
  };

  // Not used since metadata input is disabled
  // const updateFileMetadata = (updates: Partial<ModelFile>) => {
  //   if (selectedFile) {
  //     setSelectedFile({ ...selectedFile, ...updates });
  //   }
  // };

  const removeFile = () => {
    setSelectedFile(null);
    setUploadStatus('pending');
    setUploadProgress(0);
    setUploadError(undefined);
  };

  // Modified: only care that a file exists and status is pending.
  const canUpload = () => {
    return !!selectedFile && uploadStatus === 'pending';
  };


  // --- THE UPLOAD LOGIC ---
  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploadStatus('uploading');
    setUploadProgress(0);
    setUploadError(undefined);

    try {
      // 1. START
      const startRes = await axios.post(`${API_BASE_URL}/api/ingest/start`);
      const sessionId = startRes.data.session_id;
      
      if (!sessionId) throw new Error("Failed to initialize session ID");

      // 2. READ
      const fileContent = await readFileAsText(selectedFile.file);
      const allLines = fileContent.split(/\r\n|\n/);
      const totalLines = allLines.length;
      
      // 3. BATCH
      for (let i = 0; i < totalLines; i += BATCH_SIZE) {
        const chunk = allLines.slice(i, i + BATCH_SIZE);
        const validLines = chunk.filter(line => line.trim().length > 0);
        
        if (validLines.length > 0) {
           await axios.post(`${API_BASE_URL}/api/ingest/batch`, {
             session_id: sessionId,
             lines: validLines
           });
        }
        const percentComplete = Math.round(((i + chunk.length) / totalLines) * 100);
        setUploadProgress(percentComplete);
      }

      // 4. FINISH
      await axios.post(`${API_BASE_URL}/api/ingest/finish`, {
        session_id: sessionId
      });

      setUploadStatus('complete');
      setUploadProgress(100);

      // 5. NAVIGATE (after a short delay to let analysis start)
      setTimeout(() => {
        if (onAnalysisFinished) {
          onAnalysisFinished(sessionId);
        } else {
          navigate(`/results/${sessionId}`);
        }
      }, 500);

    } catch (error: any) {
      console.error(error);
      setUploadStatus('error');
      const msg = error.response?.data?.detail || error.message || 'Upload failed';
      setUploadError(msg);
    }
  };

  // Helper to read file content
  const readFileAsText = (file: File): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = (e) => resolve((e.target?.result as string) || '');
      reader.onerror = (e) => reject(e);
      reader.readAsText(file);
    });
  };

  return (
    <div className="upload-wizard">
      <div className="upload-wizard-header">
        <h1>Upload MBSE Model</h1>
        <p className="upload-subtitle">Upload manually or use the Cameo plugin</p>
      </div>

      <div className="upload-wizard-content">
        {!selectedFile ? (
          <FileDrop
            onFilesSelected={handleFilesSelected}
            acceptedFileTypes={['.json', '.xmi', '.xml', '.txt']}
            maxFiles={1}
          />
        ) : (
          <div className="file-configuration">
            <div className="file-config-item">
              <div className="file-config-header">
                <div className="file-info">
                  <span className="file-name">{selectedFile.file.name}</span>
                  <span className="file-size">
                    {(selectedFile.file.size / 1024 / 1024).toFixed(2)} MB
                  </span>
                </div>
                {uploadStatus === 'pending' && (
                  <button onClick={removeFile} className="remove-file-button">✕</button>
                )}
              </div>
              
              {/* Commented out to disable manual metadata input for now */}
              {/* <div className="file-config-fields">
                <div className="field-group">
                  <label htmlFor="vendor-select">Vendor *</label>
                  <select
                    id="vendor-select"
                    value={selectedFile.vendor}
                    onChange={(e) => updateFileMetadata({ vendor: e.target.value as 'sparx' | 'cameo' })}
                    className="vendor-select"
                    disabled={uploadStatus !== 'pending'}
                  >
                    <option value="sparx">Sparx Systems</option>
                    <option value="cameo">Cameo Systems Modeler</option>
                  </select>
                </div>

                <div className="field-group">
                  <label htmlFor="version-input">Version *</label>
                  <input
                    id="version-input"
                    type="text"
                    placeholder="e.g., 17.1"
                    value={selectedFile.version}
                    onChange={(e) => updateFileMetadata({ version: e.target.value })}
                    className="version-input"
                    disabled={uploadStatus !== 'pending'}
                  />
                </div>

                <div className="field-group">
                  <label htmlFor="model-id-input">Model ID (optional)</label>
                  <input
                    id="model-id-input"
                    type="text"
                    placeholder="e.g., CAR-001"
                    value={selectedFile.modelId || ''}
                    onChange={(e) => updateFileMetadata({ modelId: e.target.value })}
                    className="model-id-input"
                    disabled={uploadStatus !== 'pending'}
                  />
                </div>
              </div> */}

              {uploadStatus !== 'pending' && (
                <div className="upload-status-section">
                  <UploadItemStatus
                    status={uploadStatus}
                    progress={uploadProgress}
                    message={uploadError}
                  />
                </div>
              )}

              {uploadStatus === 'pending' && (
                <button
                  onClick={handleUpload}
                  className="button-primary upload-button"
                  disabled={!canUpload()}
                >
                  Analyze Model
                </button>
              )}

              {/* Disabled since we only analyze 1 model at a time */}
              {/* {uploadStatus === 'complete' && (
                <button onClick={removeFile} className="button-primary">
                  Upload Another Model
                </button>
              )} */}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}