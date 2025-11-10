import { useState } from 'react';
import { uploadAndAnalyze, type AnalyzeResponse } from '../../services/upload-service';
import FileDrop from '../shared/file-drop/file-drop';
import UploadItemStatus, { type UploadStatus } from './components/upload-item-status/upload-item-status';
import './upload-wizard.css';

interface ModelFile {
  file: File;
  vendor: 'sparx' | 'cameo';
  version: string;
  modelId?: string;
}

export default function UploadWizard() {
  const [selectedFile, setSelectedFile] = useState<ModelFile | null>(null);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('pending');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState<string | undefined>();
  const [analysisResult, setAnalysisResult] = useState<AnalyzeResponse | null>(null);

  const handleFilesSelected = (files: File[]) => {
    if (files.length > 0) {
      setSelectedFile({
        file: files[0],
        vendor: 'sparx', // default
        version: '',
        modelId: ''
      });
      // Reset upload state when new file is selected
      setUploadStatus('pending');
      setUploadProgress(0);
      setUploadError(undefined);
      setAnalysisResult(null);
    }
  };

  const updateFileMetadata = (updates: Partial<ModelFile>) => {
    if (selectedFile) {
      setSelectedFile({ ...selectedFile, ...updates });
    }
  };

  const removeFile = () => {
    setSelectedFile(null);
    setUploadStatus('pending');
    setUploadProgress(0);
    setUploadError(undefined);
    setAnalysisResult(null);
  };

  const canUpload = () => {
    return selectedFile && selectedFile.vendor && selectedFile.version && uploadStatus === 'pending';
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setUploadStatus('uploading');
    setUploadProgress(0);
    setUploadError(undefined);

    try {
      const result = await uploadAndAnalyze({
        file: selectedFile.file,
        vendor: selectedFile.vendor,
        version: selectedFile.version,
        modelId: selectedFile.modelId,
        onProgress: (progress) => {
          setUploadProgress(progress);
        },
      });

      setUploadStatus('complete');
      setUploadProgress(100);
      setAnalysisResult(result);
    } catch (error) {
      setUploadStatus('error');
      setUploadError(error instanceof Error ? error.message : 'Upload failed');
    }
  };

  return (
    <div className="upload-wizard">
      <div className="upload-wizard-header">
        <h1>Upload MBSE Model</h1>
        <p className="upload-subtitle">Upload and analyze your model for maturity assessment</p>
      </div>

      <div className="upload-wizard-content">
        {!selectedFile ? (
          <FileDrop
            onFilesSelected={handleFilesSelected}
            acceptedFileTypes={['.xmi', '.xml']}
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
                  <button
                    onClick={removeFile}
                    className="remove-file-button"
                    aria-label="Remove file"
                  >
                    ✕
                  </button>
                )}
              </div>

              <div className="file-config-fields">
                <div className="field-group">
                  <label htmlFor="vendor-select">Vendor *</label>
                  <select
                    id="vendor-select"
                    value={selectedFile.vendor}
                    onChange={(e) => updateFileMetadata({
                      vendor: e.target.value as 'sparx' | 'cameo'
                    })}
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
              </div>

              {uploadStatus !== 'pending' && (
                <div className="upload-status-section">
                  <UploadItemStatus
                    status={uploadStatus}
                    progress={uploadProgress}
                    message={uploadError}
                    indeterminate={uploadStatus === 'uploading' && uploadProgress === 0}
                  />
                </div>
              )}

              {uploadStatus === 'complete' && analysisResult && (
                <div className="analysis-results">
                  <h3>Analysis Results</h3>
                  <div className="results-summary">
                    <div className="result-item">
                      <span className="result-label">Maturity Level:</span>
                      <span className="result-value">{analysisResult.maturity_level}</span>
                    </div>
                    <div className="result-item">
                      <span className="result-label">Tests Passed:</span>
                      <span className="result-value">
                        {analysisResult.summary.passed} / {analysisResult.summary.total}
                      </span>
                    </div>
                  </div>
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

              {uploadStatus === 'complete' && (
                <button
                  onClick={removeFile}
                  className="button-primary"
                >
                  Upload Another Model
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}