import React, { useCallback } from 'react';
import { useDropzone } from 'react-dropzone';
import { MdOutlineAdd, MdUpload } from 'react-icons/md';
import './file-drop.css';

interface FileDropProps {
  onFilesSelected: (files: File[]) => void;
  acceptedFileTypes?: string[];
  maxFiles?: number;
  disabled?: boolean;
}

export default function FileDrop({ 
  onFilesSelected, 
  acceptedFileTypes = ['.xmi', '.xml'],
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
      'text/xml': ['.xml', '.xmi']
    },
    maxFiles,
    disabled,
    multiple: true
  });

  return (
    <div 
      {...getRootProps()} 
      className={`dropzone ${isDragActive ? 'drag-active' : ''} ${isDragReject ? 'drag-reject' : ''} ${disabled ? 'disabled' : ''}`}
    >
      <input {...getInputProps()} />
      <div className="dropzone__content">
        <h2 className="dropzone__headline">
          {isDragActive ? 'Drop model files here' : 'Drag model files here'}
        </h2>
        <button
          type="button"
          className="dropzone__button"
          disabled={disabled}
        >
          <MdOutlineAdd className="dropzone__button-icon" />
          Add Models
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
