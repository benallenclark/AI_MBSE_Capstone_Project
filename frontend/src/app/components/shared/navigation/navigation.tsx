import { useState, useCallback } from 'react';
import './navigation.css';

interface NavigationItem {
  id: string;
  label: string;
  href: string;
}

interface NavigationProps {
  items: NavigationItem[];
  currentPath?: string;
  onNavigate?: (href: string) => void;
  className?: string;
}

export default function Navigation({
  items,
  currentPath = '/',
  onNavigate,
  className = ''
}: NavigationProps) {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  const handleItemClick = useCallback((href: string, event: React.MouseEvent) => {
    event.preventDefault();
    onNavigate?.(href);
    setIsMenuOpen(false);
  }, [onNavigate]);

  const toggleMenu = useCallback(() => {
    setIsMenuOpen(prev => !prev);
  }, []);

  return (
    <nav className={`navigation navigation--horizontal ${className}`}>
      <ul className={`navigation__list ${isMenuOpen ? 'navigation__list--open' : ''}`}>
        {items.map((item) => (
          <li key={item.id} className="navigation__item nav-item">
            <a
              href={item.href}
              className={`navigation__link ${
                currentPath === item.href ? 'navigation__link--active' : ''
              }`}
              onClick={(e) => handleItemClick(item.href, e)}
            >
              {item.label}
            </a>
          </li>
        ))}
      </ul>

      <button
        className="navigation__toggle"
        onClick={toggleMenu}
        aria-expanded={isMenuOpen}
        aria-label="Toggle navigation menu"
        type="button"
      >
        ☰
      </button>
    </nav>
  );
}
