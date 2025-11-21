import type { Meta, StoryObj } from '@storybook/react';
import ResultsPanel from './results-panel';
import { type AnalyzeResponse } from '../../services/upload-service';

const meta: Meta<typeof ResultsPanel> = {
  title: 'Components/ResultsPanel',
  component: ResultsPanel,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'], // Enables auto-generated documentation
  decorators: [
    (Story) => (
      <div style={{ maxWidth: '900px', margin: '0 auto', padding: '20px', backgroundColor: '#f3f4f6' }}>
        <Story />
      </div>
    ),
  ],
};

export default meta;
type Story = StoryObj<typeof ResultsPanel>;

// A helper to create realistic looking data without repetitive typing
const createMockData = (
  level: number, 
  passedCount: number, 
  totalCount: number, 
  vendor = "Cameo",
  modelId = "session_mock_123"
): AnalyzeResponse => {
  
  const failedCount = totalCount - passedCount;
  const results = [];

  // Generate some passed results
  for (let i = 0; i < passedCount; i++) {
    results.push({
      id: `PASS-RULE-${i + 1}`,
      mml: Math.floor(Math.random() * level) + 1,
      passed: true,
      details: {},
    });
  }

  // Generate some failed results
  for (let i = 0; i < failedCount; i++) {
    results.push({
      id: `FAIL-RULE-${i + 1}`,
      mml: Math.floor(Math.random() * 5) + 1,
      passed: false,
      error: "Constraint violation detected",
      details: {
        violation_count: Math.floor(Math.random() * 10) + 1,
        description: "Block must satisfy a requirement",
      },
    });
  }

  return {
    schema_version: "1",
    model: {
      vendor: vendor,
      version: "2024x",
      model_id: modelId,
    },
    maturity_level: level,
    summary: {
      total: totalCount,
      passed: passedCount,
      failed: failedCount,
    },
    results: results,
  };
};

// --- 3. STORIES (SCENARIOS) ---

// Scenario A: A Typical "Work in Progress" Model (Level 2)
export const Developing: Story = {
  args: {
    onUploadAnother: () => alert('Upload Another Clicked'),
    analysisData: createMockData(2, 15, 30), // 50% pass rate
  },
};