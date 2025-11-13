import { useLocation, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { type AnalyzeResponse } from '../../services/upload-service';
import Navigation from '../../components/shared/navigation/navigation';
import ResultsPanel from '../../components/results/results-panel';
import ChatPanel from '../../components/chat/chat-panel/chat-panel';
import './analysis-results.css';

export default function AnalysisResults() {
  const location = useLocation();
  const navigate = useNavigate();
  const [analysisData, setAnalysisData] = useState<AnalyzeResponse | null>(null);

  useEffect(() => {
    // Get analysis data from navigation state
    const data = location.state?.analysisData as AnalyzeResponse | undefined;
    
    if (!data) {
      // If no data, redirect back to upload page
      navigate('/');
      return;
    }
    
    setAnalysisData(data);
  }, [location.state, navigate]);

  const handleNavigate = (href: string) => {
    navigate(href);
  };

  const handleUploadAnother = () => {
    navigate('/');
  };

  if (!analysisData) {
    return (
      <div className="analysis-results-loading">
        <p>Loading analysis results...</p>
      </div>
    );
  }

  const navigationItems = [
    { id: 'upload', label: 'Upload', href: '/' },
    { id: 'results', label: 'Results', href: '/results' },
  ];

  return (
    <div className="analysis-results-page">
      <Navigation
        items={navigationItems}
        currentPath="/results"
        onNavigate={handleNavigate}
      />
      
      <div className="analysis-results-container">
        <header className="analysis-results-header">
          <h1>Analysis Results</h1>
          <div className="analysis-metadata">
            <span className="metadata-item">
              <strong>Vendor:</strong> {analysisData.model.vendor}
            </span>
            <span className="metadata-item">
              <strong>Version:</strong> {analysisData.model.version}
            </span>
          </div>
        </header>

        <div className="analysis-results-content">
          <div className="results-section">
            <ResultsPanel 
              analysisData={analysisData}
              onUploadAnother={handleUploadAnother}
            />
          </div>
          
          <div className="chat-section">
            <ChatPanel analysisData={analysisData} />
          </div>
        </div>
      </div>
    </div>
  );
}

