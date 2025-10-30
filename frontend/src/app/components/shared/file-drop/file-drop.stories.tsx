import type { Meta, StoryObj } from '@storybook/react-vite';
import { fn } from 'storybook/test';
import FileDrop from './file-drop';

const meta = {
  title: 'Components/Shared/FileDrop',
  component: FileDrop,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
  args: {
    onFilesSelected: fn(),
  },
} satisfies Meta<typeof FileDrop>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {};

export const Disabled: Story = {
  args: {
    disabled: true,
  },
};

export const CustomFileTypes: Story = {
  args: {
    acceptedFileTypes: ['.xmi', '.xml', '.uml'],
    maxFiles: 5,
  },
};