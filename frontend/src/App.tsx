import { BrowserRouter, Routes, Route } from 'react-router-dom';
import HomeDashboard from './app/pages/home-dashboard/home-dashboard';
import AnalysisResults from './app/pages/analysis-results/analysis-results';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <div className="app">
        <main className="app-content">
          <Routes>
            <Route path="/" element={<HomeDashboard />} />
            <Route path="/results" element={<AnalysisResults />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
