import type { Meta, StoryObj } from '@storybook/react-vite';
import UploadItemStatus from './upload-item-status';

const meta = {
  title: 'Components/UploadWizard/UploadItemStatus',
  component: UploadItemStatus,
  parameters: {
    layout: 'centered',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof UploadItemStatus>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    status: 'uploading',
  },
  render: () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <UploadItemStatus status="uploading" progress={25} />
      <UploadItemStatus status="uploading" progress={65} />
      <UploadItemStatus status="uploading" indeterminate={true} />
      <UploadItemStatus status="complete" />
      <UploadItemStatus status="error" message="File size exceeds maximum limit" />
      <UploadItemStatus status="error" message="Invalid file format. Expected .xml or .xmi" />
    </div>
  ),
};
