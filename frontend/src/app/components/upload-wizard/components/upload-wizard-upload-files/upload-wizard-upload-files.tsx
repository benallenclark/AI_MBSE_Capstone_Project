import { useState } from 'react';
import { uploadAndAnalyze } from '../../../../services/upload-service';
import UploadItemStatus, { type UploadStatus } from '../upload-item-status/upload-item-status';
import './upload-wizard-upload-files.css';

interface UploadItem {
  file: File;
  vendor: 'sparx' | 'cameo';
  version: string;
  modelId?: string;
  status: UploadStatus;
  progress: number;
  error?: string;
}

interface UploadWizardUploadFilesProps {
  files?: Array<{
    file: File;
    vendor: 'sparx' | 'cameo';
    version: string;
    modelId?: string;
  }>;
}

export default function UploadWizardUploadFiles({ files = [] }: UploadWizardUploadFilesProps) {
  const [uploads, setUploads] = useState<UploadItem[]>(
    files.map(f => ({ ...f, status: 'pending' as UploadStatus, progress: 0 }))
  );

  const handleUpload = async (index: number) => {
    const item = uploads[index];

    // Update status to uploading
    setUploads(prev => prev.map((u, i) =>
      i === index ? { ...u, status: 'uploading' as UploadStatus, progress: 0 } : u
    ));

    try {
      await uploadAndAnalyze({
        file: item.file,
        vendor: item.vendor,
        version: item.version,
        modelId: item.modelId,
        onProgress: (progress) => {
          // Update progress in real-time as the file uploads
          setUploads(prev => prev.map((u, i) =>
            i === index ? { ...u, progress } : u
          ));
        },
      });

      // Mark as complete when upload and analysis finish
      setUploads(prev => prev.map((u, i) =>
        i === index ? { ...u, status: 'complete' as UploadStatus, progress: 100 } : u
      ));
    } catch (error) {
      // Mark as error if upload fails
      setUploads(prev => prev.map((u, i) =>
        i === index ? {
          ...u,
          status: 'error' as UploadStatus,
          error: error instanceof Error ? error.message : 'Upload failed'
        } : u
      ));
    }
  };

  const handleUploadAll = async () => {
    // Upload all files sequentially
    for (let i = 0; i < uploads.length; i++) {
      if (uploads[i].status === 'pending') {
        await handleUpload(i);
      }
    }
  };

  return (
    <div className="upload-wizard-upload-files">
      <div className="upload-files-header">
        <h2>Upload Files</h2>
        <button
          onClick={handleUploadAll}
          disabled={uploads.every(u => u.status !== 'uploading' && u.status !== 'complete' && u.status !== 'error')}
          className="upload-all-button"
        >
          Upload All
        </button>
      </div>

      <div className="upload-files-list">
        {uploads.map((upload, index) => (
          <div key={index} className={`upload-file-item upload-file-item--${upload.status}`}>
            <div className="file-info">
              <div className="file-name-row">
                <span className="file-name">{upload.file.name}</span>
                <span className="file-size">
                  {(upload.file.size / 1024 / 1024).toFixed(2)} MB
                </span>
              </div>
              <div className="file-metadata-row">
                <span className="file-vendor">{upload.vendor}</span>
                <span className="file-version">v{upload.version}</span>
                {upload.modelId && (
                  <span className="file-model-id">ID: {upload.modelId}</span>
                )}
              </div>
            </div>

            <div className="file-status">
              <UploadItemStatus
                status={upload.status}
                progress={upload.progress}
                message={upload.error}
                indeterminate={upload.status === 'uploading' && upload.progress === 0}
              />
            </div>
          </div>
        ))}
      </div>

      {uploads.length === 0 && (
        <div className="empty-state">
          <p>No files to upload</p>
        </div>
      )}
    </div>
  );
}