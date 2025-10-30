import { MdUpload, MdInfoOutline, MdErrorOutline, MdCheck } from 'react-icons/md';
import './upload-item-status.css';

export type UploadStatus = 'pending' |'uploading' | 'complete' | 'error';

interface UploadItemStatusProps {
  status: UploadStatus;
  message?: string;
  progress?: number;
  indeterminate?: boolean;
}

export default function UploadItemStatus({ status, message, progress = 0, indeterminate = false }: UploadItemStatusProps) {
  const isUploading = () => status === 'uploading';
  const isComplete = () => status === 'complete';
  const isError = () => status === 'error';
  const showProgressBar = () => isUploading() || isComplete();
  const getStatusIcon = () => {
    switch (status) {
      case 'uploading':
        return <MdUpload className="status-icon status-icon--uploading" />;
      case 'complete':
        return <MdCheck className="status-icon status-icon--complete" />;
      case 'error':
        return <MdErrorOutline className="status-icon status-icon--error" />;
      default:
        return <MdInfoOutline className="status-icon status-icon--pending" />;
    }
  };

  const displayProgress = isComplete() ? 100 : progress;

  return (
    <div className={`status-cell-container status-cell-container--${status}`}>
      <div className="status-icon-wrapper">
        {getStatusIcon()}
      </div>
      <div className="status-content">
        {showProgressBar() && (
          <div className="progress-bar-container">
            {indeterminate ? (
              <div className="progress-bar-fill progress-bar-fill--indeterminate" />
            ) : (
              <div
                className={`progress-bar-fill ${isComplete() ? 'progress-bar-fill--complete' : ''}`}
                style={{ width: `${Math.min(100, Math.max(0, displayProgress))}%` }}
              />
            )}
          </div>
        )}
        {isError() && message && (
          <span className="error-message">{message}</span>
        )}
      </div>
    </div>
  );
}