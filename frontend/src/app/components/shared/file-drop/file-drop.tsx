import { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { MdOutlineAdd } from 'react-icons/md';
import './file-drop.css';

interface FileDropProps {
  onFilesSelected: (files: File[]) => void;
  acceptedFileTypes?: string[];
  maxFiles?: number;
  disabled?: boolean;
}

export default function FileDrop({ 
  onFilesSelected, 
  acceptedFileTypes = ['.xmi', '.xml', '.json', '.jsonl'],
  maxFiles = 10,
  disabled = false 
}: FileDropProps) {
  const onDrop = useCallback((acceptedFiles: File[]) => {
    onFilesSelected(acceptedFiles);
  }, [onFilesSelected]);
  
  const { getRootProps, getInputProps, isDragActive, isDragReject } = useDropzone({
    onDrop,
    accept: {
      'application/xml': ['.xml', '.xmi'],
      'text/xml': ['.xml', '.xmi'],
      'application/json': ['.json', '.jsonl'],
      'text/plain': ['.jsonl', '.txt'], // just in case jsonl files are labeled as plain text
      'application/x-jsonlines': ['.jsonl']
    },
    maxFiles,
    disabled,
    multiple: true
  });

  const isSingleFile = maxFiles === 1;

  return (
    <div
      {...getRootProps()}
      className={`dropzone ${isDragActive ? 'drag-active' : ''} ${isDragReject ? 'drag-reject' : ''} ${disabled ? 'disabled' : ''}`}
    >
      <input {...getInputProps()} />
      <div className="dropzone__content">
        <h2 className="dropzone__headline">
          {isDragActive
            ? `Drop ${isSingleFile ? 'model file' : 'model files'} here`
            : `Drag ${isSingleFile ? 'model file' : 'model files'} here`}
        </h2>
        <button
          type="button"
          className="dropzone__button"
          disabled={disabled}
        >
          <MdOutlineAdd className="dropzone__button-icon" />
          {isSingleFile ? 'Add Model' : 'Add Models'}
        </button>
        <p className="dropzone__description">
          Accepted file types: {acceptedFileTypes.join(', ')}
        </p>
        {isDragReject && (
          <p className="dropzone__error">
            Some files are not supported
          </p>
        )}
      </div>
    </div>
  );
}
