import type { Meta, StoryObj } from '@storybook/react-vite';
import ChatMessage from './chat-message';

const meta = {
  title: 'Components/Chat/ChatMessage',
  component: ChatMessage,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
} satisfies Meta<typeof ChatMessage>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    message: {
        role: 'user',
        content: 'Hello, how can I help you?',
        id: '',
        timestamp: new Date(),
    },
  },
};  
