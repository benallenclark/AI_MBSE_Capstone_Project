import { useNavigate } from 'react-router-dom';
import Navigation from '../../components/shared/navigation/navigation';
import UploadWizard from '../../components/upload-wizard/upload-wizard';
import './home-dashboard.css';

export default function HomeDashboard() {
  const navigate = useNavigate();

  const handleNavigate = (href: string) => {
    navigate(href);
  };

  const navigationItems = [
    { id: 'upload', label: 'Upload', href: '/' },
    { id: 'results', label: 'Results', href: '/results' },
  ];

  return (
    <div className="home-dashboard">
      <Navigation
        items={navigationItems}
        currentPath="/"
        onNavigate={handleNavigate}
      />
      <UploadWizard />
    </div>
  );
}

