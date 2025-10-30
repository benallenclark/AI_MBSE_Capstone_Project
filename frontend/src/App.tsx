import { useState, useEffect } from 'react';
import Navigation from './app/components/shared/navigation/navigation';
import HomeDashboard from './app/pages/home-dashboard/home-dashboard';
import Upload from './app/pages/upload/upload';
import './App.css';

function App() {
  const [currentPath, setCurrentPath] = useState(window.location.pathname);

  const navigationItems = [
    { id: 'home', label: 'Home', href: '/' },
    { id: 'upload', label: 'Upload', href: '/upload' },
    { id: 'analyze', label: 'Analyze', href: '/analyze' },
  ];

  const handleNavigate = (href: string) => {
    setCurrentPath(href);
    window.history.pushState({}, '', href);
  };

  // Handle browser back/forward buttons
  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(window.location.pathname);
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  return (
    <div className="app">
      <Navigation
        items={navigationItems}
        currentPath={currentPath}
        onNavigate={handleNavigate}
      />
      <main className="app-content">
        {currentPath === '/' && <HomeDashboard />}
        {currentPath === '/upload' && <Upload />}
        {currentPath === '/analyze' && <div>Analyze page - not implemented yet</div>}
      </main>
    </div>
  );
}

export default App;
