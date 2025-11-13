import { type AnalyzeResponse } from '../../services/upload-service';
import { MdCheckCircle, MdCancel, MdInfoOutline, MdAnalytics, MdGrading, MdFileDownload, MdUpload, MdNoteAdd } from 'react-icons/md';
import { BiExport } from "react-icons/bi";
import './results-panel.css';

interface ResultsPanelProps {
  analysisData: AnalyzeResponse;
  onUploadAnother: () => void;
}

export default function ResultsPanel({ analysisData, onUploadAnother }: ResultsPanelProps) {
  const { maturity_level, summary, results } = analysisData;
  
  const getMaturityLevelLabel = (level: number): string => {
    const labels: Record<number, string> = {
      1: 'Initial',
      2: 'Developing',
      3: 'Managed',
      4: 'Integrated',
      5: 'Optimized',
    };
    return labels[level] || 'Unknown';
  };

  const getMaturityLevelDescription = (level: number): string => {
    const descriptions: Record<number, string> = {
      1: 'Basic model structure exists with minimal organization',
      2: 'Model has defined structure and some relationships',
      3: 'Model is well-organized with clear relationships and constraints',
      4: 'Model is fully integrated with comprehensive validation',
      5: 'Model demonstrates best practices and optimization',
    };
    return descriptions[level] || '';
  };

  const passRate = summary.total > 0
    ? Math.round((summary.passed / summary.total) * 100)
    : 0;

  // Calculate the percentage for the circular progress (maturity level out of 5)
  const maturityPercentage = (maturity_level / 5) * 100;

  // Calculate the stroke-dashoffset for the circular progress
  // Circumference = 2 * π * radius (radius = 54 for a 120px circle with 6px stroke)
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (maturityPercentage / 100) * circumference;

  return (
    <div className="results-panel">
      {/* Maturity Score Card */}
      <div className="maturity-card">
        <div className="maturity-header">
          <div className="maturity-icon">
            <MdAnalytics />
          </div>
          <h2>Maturity Assessment</h2>
        </div>

        <div className="maturity-score">
          <div className="score-circle-container">
            {/* SVG Circular Progress Bar */}
            <svg className="progress-ring" width="132" height="132">
              <defs>
                <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#ef4444" />
                  <stop offset="50%" stopColor="#eab308" />
                  <stop offset="100%" stopColor="#22c55e" />
                </linearGradient>
              </defs>
              {/* Background circle */}
              <circle
                className="progress-ring-bg"
                stroke="#e5e7eb"
                strokeWidth="6"
                fill="transparent"
                r={radius}
                cx="66"
                cy="66"
              />
              {/* Progress circle */}
              <circle
                className="progress-ring-circle"
                stroke="url(#progressGradient)"
                strokeWidth="6"
                fill="transparent"
                r={radius}
                cx="66"
                cy="66"
                style={{
                  strokeDasharray: circumference,
                  strokeDashoffset: strokeDashoffset,
                }}
              />
            </svg>
            {/* Score display in the center */}
            <div className="score-circle">
              <span className="score-text">
                <span className="score-number">{maturity_level}</span>
                <span className="score-max">/5</span>
              </span>
            </div>
          </div>
          <div className="score-details">
            <h3 className="maturity-label">{getMaturityLevelLabel(maturity_level)}</h3>
            <p className="maturity-description">
              {getMaturityLevelDescription(maturity_level)}
            </p>
          </div>
        </div>

        <div className="maturity-stats">
          <div className="stat-item">
            <span className="stat-label">Tests Passed</span>
            <span className="stat-value stat-value-success">
              {summary.passed} / {summary.total}
            </span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Pass Rate</span>
            <span className="stat-value">{passRate}%</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Tests Failed</span>
            <span className="stat-value stat-value-error">{summary.failed}</span>
          </div>
        </div>

        {/* Progress Bar */}
        <div className="progress-bar-container">
          <div 
            className="progress-bar-fill" 
            style={{ width: `${passRate}%` }}
          />
        </div>
      </div>

      {/* Detailed Test Results */}
      <div className="test-results-card">
        <div className="test-results-header">
          <div className="test-results-icon">
            <MdGrading />
          </div>
          <h2>Detailed Test Results</h2>
        </div>
        
        <div className="test-results-list">
          {results.map((result) => (
            <div 
              key={result.id} 
              className={`test-result-item ${result.passed ? 'test-passed' : 'test-failed'}`}
            >
              <div className="test-result-header">
                <div className="test-result-icon">
                  {result.passed ? (
                    <MdCheckCircle className="icon-success" />
                  ) : (
                    <MdCancel className="icon-error" />
                  )}
                </div>
                <div className="test-result-info">
                  <h4 className="test-result-title">
                    MML{result.mml}: {result.id}
                  </h4>
                  <span className={`test-result-status ${result.passed ? 'status-passed' : 'status-failed'}`}>
                    {result.passed ? 'Passed' : 'Failed'}
                  </span>
                </div>
              </div>
              
              {result.error && (
                <div className="test-result-error">
                  <MdInfoOutline className="icon-info" />
                  <span>{result.error}</span>
                </div>
              )}
              
              {result.details && Object.keys(result.details).length > 0 && (
                <div className="test-result-details">
                  <details>
                    <summary>View Details</summary>
                    <pre className="details-content">
                      {JSON.stringify(result.details, null, 2)}
                    </pre>
                  </details>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="results-actions">
        <button
          className="button-secondary"
          onClick={() => window.print()}
        >
          <BiExport className="button-icon" />
          Export Results
        </button>
        <button
          className="button-primary"
          onClick={onUploadAnother}
        >
          <MdNoteAdd className="button-icon" />
          Upload Another Model
        </button>
      </div>
    </div>
  );
}

