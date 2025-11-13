import type { Meta, StoryObj } from '@storybook/react-vite';
import Upload from './upload';

const meta = {
  title: 'Pages/Upload',
  component: Upload,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof Upload>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {},
};
