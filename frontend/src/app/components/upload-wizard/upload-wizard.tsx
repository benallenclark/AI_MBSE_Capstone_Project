import { useState } from 'react';
import FileDrop from '../shared/file-drop/file-drop';
import UploadWizardUploadFiles from './components/upload-wizard-upload-files/upload-wizard-upload-files';
import './upload-wizard.css';

interface ModelFile {
  file: File;
  vendor: 'sparx' | 'cameo';
  version: string;
  modelId?: string;
}

type WizardStep = 'add-models' | 'upload-models' | 'complete';

export default function UploadWizard() {
  const [currentStep, setCurrentStep] = useState<WizardStep>('add-models');
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

  const handleNext = () => {
    if (currentStep === 'add-models') {
      setCurrentStep('upload-models');
    }
  };

  const handleBack = () => {
    if (currentStep === 'upload-models') {
      setCurrentStep('add-models');
    } else if (currentStep === 'complete') {
      setCurrentStep('upload-models');
    }
  };

  const canProceed = () => {
    if (currentStep === 'add-models') {
      return selectedFiles.every(f => f.vendor && f.version) && selectedFiles.length > 0;
    }
    return true;
  };

  const resetWizard = () => {
    setCurrentStep('add-models');
    setSelectedFiles([]);
  };

  return (
    <div className="upload-wizard">
      <div className="upload-wizard-header">
        <div className="wizard-steps">
          <div className={`step ${currentStep === 'add-models' ? 'active' : ''} ${currentStep === 'upload-models' || currentStep === 'complete' ? 'completed' : ''}`}>
            <span className="step-number">1</span>
            <span className="step-label">Add Models</span>
          </div>
          <div className="step-divider" />
          <div className={`step ${currentStep === 'upload-models' ? 'active' : ''} ${currentStep === 'complete' ? 'completed' : ''}`}>
            <span className="step-number">2</span>
            <span className="step-label">Upload Models</span>
          </div>
          <div className="step-divider" />
          <div className={`step ${currentStep === 'complete' ? 'active' : ''}`}>
            <span className="step-number">3</span>
            <span className="step-label">Complete</span>
          </div>
        </div>
      </div>

      <div className="upload-wizard-content">
        {/* Step 1: Add Models */}
        {currentStep === 'add-models' && (
          <div className="wizard-step-content">
            <FileDrop
              onFilesSelected={handleFilesSelected}
              acceptedFileTypes={['.xmi', '.xml']}
            />

            {selectedFiles.length > 0 && (
              <div className="file-configuration-list" style={{ marginTop: '32px' }}>
                {selectedFiles.map((modelFile, index) => (
                  <div key={index} className="file-config-item">
                    <div className="file-config-header">
                      <span className="file-name">{modelFile.file.name}</span>
                      <span className="file-size">
                        {(modelFile.file.size / 1024 / 1024).toFixed(2)} MB
                      </span>
                    </div>

                    <div className="file-config-fields">
                      <div className="field-group">
                        <label>Vendor</label>
                        <select
                          value={modelFile.vendor}
                          onChange={(e) => updateFileMetadata(index, {
                            vendor: e.target.value as 'sparx' | 'cameo'
                          })}
                          className="vendor-select"
                        >
                          <option value="sparx">Sparx Systems</option>
                          <option value="cameo">Cameo Systems Modeler</option>
                        </select>
                      </div>

                      <div className="field-group">
                        <label>Version *</label>
                        <input
                          type="text"
                          placeholder="e.g., 17.1"
                          value={modelFile.version}
                          onChange={(e) => updateFileMetadata(index, { version: e.target.value })}
                          className="version-input"
                        />
                      </div>

                      <div className="field-group">
                        <label>Model ID (optional)</label>
                        <input
                          type="text"
                          placeholder="e.g., model-001"
                          value={modelFile.modelId}
                          onChange={(e) => updateFileMetadata(index, { modelId: e.target.value })}
                          className="model-id-input"
                        />
                      </div>

                      <button
                        onClick={() => removeFile(index)}
                        className="remove-button"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Step 2: Upload Models */}
        {currentStep === 'upload-models' && (
          <div className="wizard-step-content">
            <UploadWizardUploadFiles files={selectedFiles} />
          </div>
        )}

        {/* Step 3: Complete */}
        {currentStep === 'complete' && (
          <div className="wizard-step-content">
            <div className="complete-message">
              <h2>Upload Complete!</h2>
              <p>All models have been successfully uploaded and analyzed.</p>
            </div>
          </div>
        )}
      </div>

      <div className="upload-wizard-footer">
        <div className="footer-actions">
          {currentStep !== 'add-models' && currentStep !== 'complete' && (
            <button onClick={handleBack} className="button-secondary">
              Back
            </button>
          )}

          {currentStep === 'add-models' && (
            <button
              onClick={handleNext}
              className="button-primary"
              disabled={!canProceed()}
            >
              Start Upload
            </button>
          )}

          {currentStep === 'upload-models' && (
            <button
              onClick={() => setCurrentStep('complete')}
              className="button-primary"
            >
              View Results
            </button>
          )}

          {currentStep === 'complete' && (
            <button onClick={resetWizard} className="button-primary">
              Upload More Models
            </button>
          )}
        </div>
      </div>
    </div>
  );
}