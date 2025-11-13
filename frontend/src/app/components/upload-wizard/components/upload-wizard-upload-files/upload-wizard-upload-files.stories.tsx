import type { Meta, StoryObj } from '@storybook/react-vite';
import UploadWizardUploadFiles from './upload-wizard-upload-files';
import UploadItemStatus from '../upload-item-status/upload-item-status';
import './upload-wizard-upload-files.css';

const meta = {
  title: 'Components/UploadWizard/UploadWizardUploadFiles',
  component: UploadWizardUploadFiles,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof UploadWizardUploadFiles>;

export default meta;
type Story = StoryObj<typeof meta>;

// Create mock files for the story
const createMockFile = (name: string, size: number): File => {
  const blob = new Blob(['x'.repeat(size)], { type: 'application/xml' });
  return new File([blob], name, { type: 'application/xml' });
};

const mockFilesReady = [
  {
    file: createMockFile('DellSat-77_System.xml', 1024 * 1024 * 2.5),
    vendor: 'sparx' as const,
    version: '17.1',
    modelId: 'model-001',
  },
  {
    file: createMockFile('SatelliteModel.xmi', 1024 * 1024 * 4.2),
    vendor: 'cameo' as const,
    version: '19.0',
    modelId: 'model-002',
  },
  {
    file: createMockFile('SystemArchitecture.xml', 1024 * 1024 * 1.8),
    vendor: 'sparx' as const,
    version: '16.5',
  },
];

export const Default: Story = {
  args: {
    files: mockFilesReady,
  },
};

// Mock component that doesn't use the upload service
const MockUploadWizardUploadFiles = ({ files }: any) => {
  const mockUploads = files.map((f: any) => ({
    ...f,
    status: f.status || 'pending',
    progress: f.progress || 0,
  }));

  return (
    <div className="upload-wizard-upload-files">
      <div className="upload-files-header">
        <h2>Upload Files</h2>
        <button className="upload-all-button">Upload All</button>
      </div>

      <div className="upload-files-list">
        {mockUploads.map((upload: any, index: number) => (
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
                indeterminate={upload.indeterminate || (upload.status === 'uploading' && upload.progress === 0)}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export const UploadingStates: Story = {
  render: () => {
    const mockFiles = [
      {
        file: createMockFile('DellSat-77_System.xml', 1024 * 1024 * 2.5),
        vendor: 'sparx' as const,
        version: '17.1',
        modelId: 'model-001',
        status: 'uploading' as const,
        progress: 35,
      },
      {
        file: createMockFile('SatelliteModel.xmi', 1024 * 1024 * 4.2),
        vendor: 'cameo' as const,
        version: '19.0',
        modelId: 'model-002',
        status: 'uploading' as const,
        progress: 0,
        indeterminate: true,
      },
      {
        file: createMockFile('SystemArchitecture.xml', 1024 * 1024 * 1.8),
        vendor: 'sparx' as const,
        version: '16.5',
        status: 'complete' as const,
        progress: 100,
      },
      {
        file: createMockFile('InvalidModel.xml', 1024 * 1024 * 3.1),
        vendor: 'cameo' as const,
        version: '18.5',
        modelId: 'model-004',
        status: 'error' as const,
        progress: 0,
        error: 'File validation failed: Invalid XML structure',
      },
    ];

    return <MockUploadWizardUploadFiles files={mockFiles} />;
  },
};

export const Empty: Story = {
  args: {
    files: [],
  },
};
