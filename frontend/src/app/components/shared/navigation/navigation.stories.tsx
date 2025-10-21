import type { Meta, StoryObj } from '@storybook/react-vite';
import { fn } from 'storybook/test';
import Navigation from './navigation';

const meta = {
  title: 'Components/Navigation',
  component: Navigation,
  parameters: {
    layout: 'fullscreen',
  },
  tags: ['autodocs'],
  argTypes: {
    currentPath: {
      control: { type: 'text' },
    },
  },
  args: {
    onNavigate: fn(),
  },
} satisfies Meta<typeof Navigation>;

export default meta;
type Story = StoryObj<typeof meta>;

const defaultItems = [
  { id: 'home', label: 'Home', href: '/' },
  { id: 'upload', label: 'Upload', href: '/upload' },
  { id: 'analyze', label: 'Analyze', href: '/analyze' },
];

export const Horizontal: Story = {
  args: {
    items: defaultItems,
    currentPath: '/',
  },
};

export const MinimalItems: Story = {
  args: {
    items: [
      { id: 'home', label: 'Home', href: '/' },
    ],
    currentPath: '/',
  },
};

