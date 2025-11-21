import { type AnalyzeResponse } from '../../services/upload-service';
import { MdCheckCircle, MdCancel, MdInfoOutline, MdAnalytics, MdGrading, MdOpenInNew, MdNoteAdd, MdList, MdViewModule } from 'react-icons/md';
import { BiExport } from "react-icons/bi";
import './results-panel.css';
import { useMemo, useState } from 'react';

interface ResultsPanelProps {
  analysisData: AnalyzeResponse;
  onUploadAnother: () => void;
}

export default function ResultsPanel({ analysisData, onUploadAnother }: ResultsPanelProps) {
  // --- Toggle View STATE ---
  const [viewMode, setViewMode] = useState<'tests' | 'capabilities'>('tests');

  const maxMaturityLevel = 9;
  const { maturity_level, summary, results, model } = analysisData;
  
  const API_BASE = "http://localhost:8000"; 
  const reportBaseUrl = `${API_BASE}/api/report/${model?.model_id || 'latest'}`;

  // Helper functions to get labels and descriptions
  const getMaturityLevelLabel = (level: number): string => {
    const labels: Record<number, string> = {
      1: 'Intent Captured',
      2: 'Structural Foundation',
      3: 'Behavioral Foundation',
      4: 'Foundational Traceability',
      5: 'Trade-off Analysis',
      6: 'Simulation & Tuning',
      7: 'Verification & Validation',
      8: 'Lifecycle Change Control',
      9: 'Digital Twin Integration',
    };
    return labels[level] || 'Unknown';
  };

  // Description texts for each maturity level
  const getMaturityLevelDescription = (level: number): string => {
    const descriptions: Record<number, string> = {
      1: 'The model can capture, manage, and decompose stakeholder/system needs into a traceable requirements hierarchy.',
      2: 'The model can define components, hierarchy, and interfaces as a coherent structural blueprint (ICD-ready).',
      3: 'The model can specify scenarios, flows, and states and allocate them to structure for executable, testable behavior.',
      4: 'The model can link intent, structure, and behavior to enable end-to-end traceability and impact analysis.',
      5: 'The model can represent alternatives and evaluation criteria to run trade studies against baseline requirements.',
      6: 'The model can bind constraints/parametrics and run simulations for early performance validation and tuning.',
      7: 'The model can link tests to requirements to automate coverage, generate procedures, and support safety analysis.',
      8: 'The model can automate change-impact analysis and manage configuration via formal change packages across the digital thread.',
      9: 'The model can bind live operational data to maintain a calibrated, predictive digital twin.',
    };
    return descriptions[level] ?? '';
  };

  // Group results by maturity level
  const groupedResults = useMemo(() => {
    const groups = new Map<number, typeof results>();
    results.forEach((r) => {
      const current = groups.get(r.mml) || [];
      current.push(r);
      groups.set(r.mml, current);
    });
    return Array.from(groups.keys())
      .sort((a, b) => a - b)
      .map((level) => ({
        level,
        label: getMaturityLevelLabel(level),
        items: groups.get(level) || [],
      }));
  }, [results]);

  // Linear list of results for Capabilities view
  const linearResults = useMemo(() => {
    // Sort by maturity level first, then by id
    return [...results].sort((a, b) => {
      if (a.mml !== b.mml) return a.mml - b.mml;
      return (a.id || '').localeCompare(b.id || '');
    });
  }, [results]);

  const passRate = summary.total > 0
    ? Math.round((summary.passed / summary.total) * 100)
    : 0;

  const maturityPercentage = (maturity_level / maxMaturityLevel) * 100;
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
            <svg className="progress-ring" width="132" height="132">
              <defs>
                <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#ef4444" />
                  <stop offset="50%" stopColor="#eab308" />
                  <stop offset="100%" stopColor="#22c55e" />
                </linearGradient>
              </defs>
              <circle className="progress-ring-bg" stroke="#e5e7eb" strokeWidth="6" fill="transparent" r={radius} cx="66" cy="66" />
              <circle
                className="progress-ring-circle"
                stroke="url(#progressGradient)"
                strokeWidth="6"
                fill="transparent"
                r={radius}
                cx="66"
                cy="66"
                style={{ strokeDasharray: circumference, strokeDashoffset: strokeDashoffset }}
              />
            </svg>
            <div className="score-circle">
              <span className="score-text">
                <span className="score-number">{maturity_level}</span>
                <span className="score-max">/{maxMaturityLevel}</span>
              </span>
            </div>
          </div>
          <div className="score-details">
            <h3 className="maturity-label">{getMaturityLevelLabel(maturity_level)}</h3>
            <p className="maturity-description">{getMaturityLevelDescription(maturity_level)}</p>
          </div>
        </div>

        <div className="maturity-stats">
          <div className="stat-item">
            <span className="stat-label">Tests Passed</span>
            <span className="stat-value stat-value-success">{summary.passed} / {summary.total}</span>
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
        
        <div className="progress-bar-container">
          <div className="progress-bar-fill" style={{ width: `${passRate}%` }} />
        </div>
      </div>

      {/* Detailed Results Card with Toggle */}
      <div className="test-results-card">
        <div className="test-results-header">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div className="test-results-icon">
              <MdGrading />
            </div>
            {/* Dynamic Title based on View */}
            <h2>{viewMode === 'tests' ? 'Detailed Test Results' : 'Model Capabilities'}</h2>
          </div>

          {/* --- Toggle View Buttons --- */}
          <div className="view-toggle" style={{ display: 'flex', gap: '0.5rem', background: '#f3f4f6', padding: '4px', borderRadius: '8px' }}>
            <button 
              onClick={() => setViewMode('tests')}
              style={{
                display: 'flex', alignItems: 'center', gap: '4px',
                padding: '6px 12px', borderRadius: '6px', border: 'none', cursor: 'pointer',
                background: viewMode === 'tests' ? '#fff' : 'transparent',
                boxShadow: viewMode === 'tests' ? '0 1px 2px rgba(0,0,0,0.1)' : 'none',
                fontWeight: 500, color: viewMode === 'tests' ? '#1f2937' : '#6b7280'
              }}
            >
              <MdViewModule /> Tests
            </button>
            <button 
              onClick={() => setViewMode('capabilities')}
              style={{
                display: 'flex', alignItems: 'center', gap: '4px',
                padding: '6px 12px', borderRadius: '6px', border: 'none', cursor: 'pointer',
                background: viewMode === 'capabilities' ? '#fff' : 'transparent',
                boxShadow: viewMode === 'capabilities' ? '0 1px 2px rgba(0,0,0,0.1)' : 'none',
                fontWeight: 500, color: viewMode === 'capabilities' ? '#1f2937' : '#6b7280'
              }}
            >
              <MdList /> Capabilities
            </button>
          </div>
        </div>
        
        <div className="test-results-list">
          {/* --- CONDITIONAL RENDERING --- */}
          
          {/* VIEW 1: TESTS */}
          {viewMode === 'tests' && groupedResults.map((group) => (
            <details key={group.level} className="level-group-container" style={{ marginBottom: '1rem' }}>
              <summary style={{ cursor: 'pointer', padding: '10px', fontWeight: 'bold', backgroundColor: '#f9fafb', borderRadius: '6px', marginBottom: '8px' }}>
                Level {group.level}: {group.label} ({group.items.filter(i => i.passed).length}/{group.items.length} Passed)
              </summary>
              
              {group.items.map((result) => (
                <div 
                  key={result.id} 
                  className={`test-result-item ${result.passed ? 'test-passed' : 'test-failed'}`}
                  style={{ marginLeft: '1rem' }}
                >
                  <div className="test-result-header">
                    <div className="test-result-icon">
                      {result.passed ? <MdCheckCircle className="icon-success" /> : <MdCancel className="icon-error" />}
                    </div>
                    <div className="test-result-info">
                      <h4 className="test-result-title">{result.id}</h4>
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

                  {!result.passed && (
                    <div className="test-result-actions" style={{ marginTop: '0.5rem', paddingLeft: '2rem' }}>
                      <a 
                        href={`${reportBaseUrl}?rule=${result.id}`} 
                        target="_blank" 
                        rel="noopener noreferrer"
                        className="view-evidence-link"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem', color: '#2563eb', textDecoration: 'none', fontWeight: 500 }}
                      >
                        <MdOpenInNew /> View Evidence
                      </a>
                    </div>
                  )}
                </div>
              ))}
            </details>
          ))}

          {/* VIEW 2: CAPABILITIES */}
          {viewMode === 'capabilities' && (
            <div className="capabilities-list" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {linearResults.map((result, index) => (
                <div 
                  key={result.id}
                  style={{
                    display: 'flex', 
                    alignItems: 'center',
                    padding: '10px 16px',
                    borderRadius: '6px',
                    backgroundColor: '#fff',
                    border: '1px solid',
                    borderColor: result.passed ? '#bbf7d0' : '#f3f4f6', // Green border if passed, grey if not
                    opacity: result.passed ? 1 : 0.7 // Dim failed ones slightly
                  }}
                >
                  {/* Icon */}
                  <div style={{ marginRight: '12px', display: 'flex', alignItems: 'center' }}>
                    {result.passed ? (
                      <MdCheckCircle style={{ color: '#22c55e', fontSize: '1.2rem' }} />
                    ) : (
                      // Use cancel icon for failed/locked capabilities
                      <MdCancel style={{ color: '#ef4444', fontSize: '1.2rem' }} />
                    )}
                  </div>

                  {/* Text Content */}
                  <div style={{ flex: 1 }}>
                    <div style={{ 
                      fontWeight: '600', 
                      color: result.passed ? '#15803d' : '#6b7280', // Green text if passed, Grey if locked
                      textDecoration: result.passed ? 'none' : 'none' 
                    }}>
                      {/* Display ID  */}
                      {result.id}
                    </div>
                    <span style={{ fontSize: '0.75rem', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Level {result.mml} Capability
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

        </div>
      </div>

      {/* Action Buttons */}
      <div className="results-actions">
        <a
            className="button-secondary"
            href={reportBaseUrl}
            target="_blank"
            rel="noreferrer"
            style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', textDecoration: 'none' }}
        >
          <BiExport className="button-icon" />
          View All Evidence
        </a>
        <button className="button-primary" onClick={onUploadAnother}>
          <MdNoteAdd className="button-icon" />
          Upload Another Model
        </button>
      </div>
    </div>
  );
}