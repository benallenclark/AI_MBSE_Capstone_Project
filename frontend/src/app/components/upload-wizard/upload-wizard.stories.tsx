import type { Meta, StoryObj } from '@storybook/react-vite';
import UploadWizard from './upload-wizard';

const meta = {
  title: 'Components/UploadWizard',
  component: UploadWizard,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof UploadWizard>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {},
};