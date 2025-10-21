import { useState } from 'react';
import Navigation from './app/components/shared/navigation/navigation';
import HomeDashboard from './app/pages/home-dashboard/home-dashboard';
import './App.css';

function App() {
  const [currentPath, setCurrentPath] = useState('/');

  const navigationItems = [
    { id: 'home', label: 'Home', href: '/' },
    { id: 'upload', label: 'Upload', href: '/upload' },
    { id: 'analyze', label: 'Analyze', href: '/analyze' },
  ];

  const handleNavigate = (href: string) => {
    setCurrentPath(href);
  };

  return (
    <div className="app">
      <Navigation
        items={navigationItems}
        currentPath={currentPath}
        onNavigate={handleNavigate}
      />
      <main className="app-content">
        {currentPath === '/' && <HomeDashboard />}
        {currentPath === '/upload' && <div>Upload page - not implemented yet</div>}
        {currentPath === '/analyze' && <div>Analyze page - not implemented yet</div>}
      </main>
    </div>
  );
}

export default App;
