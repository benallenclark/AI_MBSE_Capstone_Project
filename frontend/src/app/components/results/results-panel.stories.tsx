import type { Meta, StoryObj } from '@storybook/react-vite';
import { fn } from 'storybook/test';
import ResultsPanel from './results-panel';

const meta = {
  title: 'Components/Results/ResultsPanel',
  component: ResultsPanel,
  parameters: {
    layout: 'padded',
  },
  tags: ['autodocs'],
  args: {
    onUploadAnother: fn(),
  },
} satisfies Meta<typeof ResultsPanel>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    analysisData: {
      schema_version: '1.0.0',
      model: {
        vendor: 'sparx',
        version: '17.1',
      },
      maturity_level: 3,
      summary: {
        total: 10,
        passed: 7,
        failed: 3,
      },
      results: [
        {
          id: 'mml_1:count_tables',
          mml: 1,
          passed: true,
          details: {
                vendor: 'sparx',
                version: '17.1',
                missing_tables: [],
                unexpected_tables: [],
                table_counts: {
                  "t_object": true,
                  "t_connector": true,
                  "t_package": true
                },
                row_counts: { "t_object": 722, "t_connector": 373, "t_package": 46 },
                total_rows: 1141,
                total_tables: 3,
          },
        },
        {
          id: 'mml_2:block_has_port',
          mml: 2,
          passed: false,
          details: {
            vendor: 'sparx',
            version: '17.1',
            blocks_total: 15,
            blocks_with_ports: 10,
            blocks_missing_ports: 5,
            counts: { "passed": 10, "failed": 5 },
            evidence: {
              "passed": [
                {
                  "block_id": 101,
                  "block_guid": "{...}",
                  "block_name": "Antenna",
                  "port_count": 3
                }
              ],
              "failed": [
                {
                  "block_id": 205,
                  "block_guid": "{...}",
                  "block_name": "PowerUnit",
                  "port_count": 0
                }
              ]
            },
            capabilities: { "sql": true, "per_block": true },
          },
        },
      ],
    },
  },
};