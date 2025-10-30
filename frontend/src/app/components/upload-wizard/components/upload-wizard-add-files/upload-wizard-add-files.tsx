import React, { useState } from 'react';
import FileDrop from '../../../shared/file-drop/file-drop';

interface ModelFile {
  file: File;
  vendor: 'sparx' | 'cameo';
  version: string;
  modelId?: string;
}

export default function UploadWizardAddFiles() {
  const [selectedFiles, setSelectedFiles] = useState<ModelFile[]>([]);

  const handleFilesSelected = (files: File[]) => {
    const newModelFiles: ModelFile[] = files.map(file => ({
      file,
      vendor: 'sparx', // default
      version: '',
      modelId: ''
    }));
    
    setSelectedFiles(prev => [...prev, ...newModelFiles]);
  };

  const updateFileMetadata = (index: number, updates: Partial<ModelFile>) => {
    setSelectedFiles(prev => prev.map((item, i) => 
      i === index ? { ...item, ...updates } : item
    ));
  };

  const removeFile = (index: number) => {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  };

  return (
    <div className='upload-wizard-add-files-container'>
      <FileDrop 
        onFilesSelected={handleFilesSelected}
        acceptedFileTypes={['.xmi', '.xml']}
      />

      {selectedFiles.length > 0 && (
        <div className="selected-files">
          <h3>Selected Files ({selectedFiles.length})</h3>
          {selectedFiles.map((modelFile, index) => (
            <div key={index} className="file-item">
              <div className="file-info">
                <span className="file-name">{modelFile.file.name}</span>
                <span className="file-size">
                  {(modelFile.file.size / 1024).toFixed(1)} KB
                </span>
              </div>
              
              <div className="file-metadata">
                <select
                  value={modelFile.vendor}
                  onChange={(e) => updateFileMetadata(index, { 
                    vendor: e.target.value as 'sparx' | 'cameo' 
                  })}
                >
                  <option value="sparx">Sparx</option>
                  <option value="cameo">Cameo</option>
                </select>
                
                <input
                  type="text"
                  placeholder="Version (e.g., 17.1)"
                  value={modelFile.version}
                  onChange={(e) => updateFileMetadata(index, { version: e.target.value })}
                />
                
                <input
                  type="text"
                  placeholder="Model ID (optional)"
                  value={modelFile.modelId}
                  onChange={(e) => updateFileMetadata(index, { modelId: e.target.value })}
                />
                
                <button onClick={() => removeFile(index)}>Remove</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}