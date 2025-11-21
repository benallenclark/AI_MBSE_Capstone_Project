import { useParams, useNavigate } from 'react-router-dom';
import { useState, useEffect } from 'react';
import { type AnalyzeResponse, getMaturityReport, toAnalyzeResponse } from '../../services/upload-service';
import Navigation from '../../components/shared/navigation/navigation';
import ResultsPanel from '../../components/results/results-panel';
import ChatPanel from '../../components/chat/chat-panel/chat-panel';
import './analysis-results.css';

export default function AnalysisResults() {
  // 1. Get the sessionId from the URL parameters
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [analysisData, setAnalysisData] = useState<AnalyzeResponse | null>(null);

  useEffect(() => {
    if (!sessionId) {
      navigate('/');
      return;
    }

    // 2. Poll the backend for the maturity report until it's ready
    const intervalId = setInterval(async () => {
      try {
        const report = await getMaturityReport(sessionId);
        if (report) {
          // 3. Convert and store the analysis data once available
          setAnalysisData(toAnalyzeResponse(report));
          clearInterval(intervalId);  // Stop polling once we have the data
        }
      } catch (error) {
        console.error("Waiting for analysis...", error);
      }
    }, 500); // Check every half second

    // 4. stop polling if user leaves the page
    return () => clearInterval(intervalId);
  }, [sessionId, navigate]);

  const handleNavigate = (href: string) => {
    navigate(href);
  };

  const handleUploadAnother = () => {
    navigate('/');
  };

  if (!analysisData) {
    return (
      <div className="analysis-results-loading">
        <div className="loading-spinner"></div>
        <p>Loading analysis results for session {sessionId}...</p>
      </div>
    );
  }

  const navigationItems = [
    { id: 'upload', label: 'Upload', href: '/' },
    // 5. Add a Results link with the current sessionId
    { id: 'results', label: 'Results', href: `/results/${sessionId}` },
  ];

  return (
    <div className="analysis-results-page">
      <Navigation
        items={navigationItems}
        currentPath={`/results/${sessionId}`} // Highlight the Results link
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
            <span className="metadata-item">
              <strong>ID:</strong> {analysisData.model.model_id}
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