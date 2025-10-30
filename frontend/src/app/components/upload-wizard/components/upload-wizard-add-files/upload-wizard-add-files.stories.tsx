import type { Meta, StoryObj } from '@storybook/react-vite';
import UploadWizardAddFiles from './upload-wizard-add-files';

const meta = {
  title: 'Components/UploadWizard/UploadWizardAddFiles',
  component: UploadWizardAddFiles,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof UploadWizardAddFiles>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {},
};
