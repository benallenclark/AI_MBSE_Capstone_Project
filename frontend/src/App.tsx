import { useEffect, useRef } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import axios from 'axios';
import Upload from './app/pages/upload/upload';
import AnalysisResults from './app/pages/analysis-results/analysis-results';

const API_BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000';
const POLLING_INTERVAL_MS = 2000;

// This compenent detects if a user uploads a model via a plugin 
// by polling the latest analysis endpoint
function PluginDetector() {
  const navigate = useNavigate();
  const location = useLocation();
  const lastSeenData = useRef<{id: string | null, timestamp: string | null, fileModified: number | null} | null>(null);
  const isNavigating = useRef<boolean>(false);

  useEffect(() => {
    console.log('[Global Polling] Started on path:', location.pathname);

    const checkForPluginUpload = async () => {
      // Don't poll if we're in the middle of navigating
      if (isNavigating.current) {
        console.log('[Global Polling] Skipped - navigation in progress');
        return;
      }

      try {
        const response = await axios.get(`${API_BASE_URL}/api/analysis/latest`);
        const data = response.data;
        
        const currentRemoteId = data?.model?.model_id || data?.meta?.session_id || null;
        const currentTimestamp = data?.meta?.timestamp || data?.timestamp || data?.created_at || null;
        const currentFileModified = data?.meta?.file_modified_at || null;

        // First poll - establish baseline
        if (lastSeenData.current === null) {
          console.log(`[Global Polling] ✓ Baseline established:`, {
            id: currentRemoteId,
            timestamp: currentTimestamp,
            fileModified: currentFileModified,
            path: location.pathname
          });
          lastSeenData.current = { 
            id: currentRemoteId, 
            timestamp: currentTimestamp,
            fileModified: currentFileModified
          };
          return;
        }

        const lastId = lastSeenData.current.id;
        const lastTime = lastSeenData.current.timestamp;
        const lastFileModified = lastSeenData.current.fileModified;

        // Detect changes
        let hasChanged = false;
        let changeReason = '';
        
        if (!lastId && currentRemoteId) {
          hasChanged = true;
          changeReason = 'New analysis appeared';
        } else if (currentRemoteId && currentRemoteId !== lastId) {
          hasChanged = true;
          changeReason = 'ID changed';
        } else if (currentRemoteId && currentTimestamp && lastTime && currentTimestamp !== lastTime) {
          hasChanged = true;
          changeReason = 'Timestamp changed';
        } else if (currentFileModified && lastFileModified && currentFileModified !== lastFileModified) {
          // This is the key detection for plugin uploads
          hasChanged = true;
          changeReason = 'File was modified (plugin upload detected)';
        }

        if (hasChanged) {
          console.log(`[Global Polling] 🚀 UPLOAD DETECTED: ${changeReason}`, {
            from: lastSeenData.current,
            to: { 
              id: currentRemoteId, 
              timestamp: currentTimestamp,
              fileModified: currentFileModified
            }
          });
          
          // Update baseline
          lastSeenData.current = { 
            id: currentRemoteId, 
            timestamp: currentTimestamp,
            fileModified: currentFileModified
          };
          
          // Only navigate if we're not already on that results page
          const currentResultsPath = `/results/${currentRemoteId}`;
          if (currentRemoteId && location.pathname !== currentResultsPath) {
            console.log('[Global Polling] Navigating to:', currentResultsPath);
            isNavigating.current = true;
            navigate(currentResultsPath);
            
            // Reset navigation flag after a delay
            setTimeout(() => {
              isNavigating.current = false;
            }, 2000);
          } else {
            console.log('[Global Polling] Already on target page, refreshing...');
            // If we're already on the page, trigger a refresh by navigating to it again
            navigate(currentResultsPath, { replace: true });
          }
        }
      } catch (error) {
        if (axios.isAxiosError(error) && error.response?.status === 404) {
          if (lastSeenData.current === null) {
            console.log("[Global Polling] ✓ Baseline: No analysis (404)");
            lastSeenData.current = { id: null, timestamp: null, fileModified: null };
          }
        } else {
          console.error("[Global Polling] ⚠️ Error:", error);
        }
      }
    };

    const intervalId = setInterval(checkForPluginUpload, POLLING_INTERVAL_MS);
    checkForPluginUpload(); // Run immediately

    return () => {
      console.log('[Global Polling] Stopped');
      clearInterval(intervalId);
    };
  }, [navigate, location.pathname]);

  return null; // This component doesn't render anything
}

export default function App() {
  return (
    <Router>
      <PluginDetector />
      <Routes>
        <Route path="/" element={<Upload />} />
        <Route path="/results/:sessionId" element={<AnalysisResults />} />
      </Routes>
    </Router>
  );
}