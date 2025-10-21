/**
 * Global color constants for the application
 */

export const colors = {
  // Primary colors
  primary: '#646cff',
  primaryHover: '#535bf2',
  primaryLight: '#747bff',

  // Neutral colors
  white: '#ffffff',
  black: '#000000',
  gray50: '#f9f9f9',
  gray100: '#f5f5f5',
  gray200: '#e0e0e0',
  gray300: '#d0d0d0',
  gray400: '#b0b0b0',
  gray500: '#808080',
  gray600: '#606060',
  gray700: '#404040',
  gray800: '#242424',
  gray900: '#1a1a1a',

  // Text colors
  textPrimary: '#213547',
  textSecondary: '#646464',
  textLight: 'rgba(255, 255, 255, 0.87)',
  textDark: '#333333',

  // Background colors
  bgLight: '#ffffff',
  bgDark: '#242424',
  bgLightAlt: '#f9f9f9',

  // Semantic colors
  success: '#22c55e',
  successHover: '#16a34a',
  warning: '#f59e0b',
  warningHover: '#d97706',
  error: '#ef4444',
  errorHover: '#dc2626',
  info: '#3b82f6',
  infoHover: '#2563eb',

  // Border colors
  border: '#e0e0e0',
  borderLight: '#f0f0f0',
  borderDark: '#303030',
} as const;

export type ColorKey = keyof typeof colors;

