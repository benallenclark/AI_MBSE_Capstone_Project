/**
 * Central export for all style constants and utilities
 */

export { colors, type ColorKey } from './colors';
export { typography, textStyles } from './typography';
export { spacing, spacingPatterns } from './spacing';

// Re-export all as a single theme object for convenience
export const theme = {
  colors: require('./colors').colors,
  typography: require('./typography').typography,
  textStyles: require('./typography').textStyles,
  spacing: require('./spacing').spacing,
  spacingPatterns: require('./spacing').spacingPatterns,
};

