/**
 * Global spacing constants for the application
 */

export const spacing = {
  // Base spacing unit (4px)
  0: '0',
  1: '0.25rem',   // 4px
  2: '0.5rem',    // 8px
  3: '0.75rem',   // 12px
  4: '1rem',      // 16px
  5: '1.25rem',   // 20px
  6: '1.5rem',    // 24px
  7: '1.75rem',   // 28px
  8: '2rem',      // 32px
  9: '2.25rem',   // 36px
  10: '2.5rem',   // 40px
  12: '3rem',     // 48px
  14: '3.5rem',   // 56px
  16: '4rem',     // 64px
  20: '5rem',     // 80px
  24: '6rem',     // 96px
  28: '7rem',     // 112px
  32: '8rem',     // 128px
  36: '9rem',     // 144px
  40: '10rem',    // 160px
  44: '11rem',    // 176px
  48: '12rem',    // 192px
  52: '13rem',    // 208px
  56: '14rem',    // 224px
  60: '15rem',    // 240px
  64: '16rem',    // 256px
  72: '18rem',    // 288px
  80: '20rem',    // 320px
  96: '24rem',    // 384px
} as const;

// Common spacing patterns
export const spacingPatterns = {
  // Padding patterns
  paddingXs: `${spacing[2]} ${spacing[3]}`,
  paddingSm: `${spacing[2]} ${spacing[4]}`,
  paddingMd: `${spacing[3]} ${spacing[4]}`,
  paddingLg: `${spacing[4]} ${spacing[6]}`,
  paddingXl: `${spacing[6]} ${spacing[8]}`,

  // Margin patterns
  marginXs: `${spacing[2]} ${spacing[3]}`,
  marginSm: `${spacing[2]} ${spacing[4]}`,
  marginMd: `${spacing[3]} ${spacing[4]}`,
  marginLg: `${spacing[4]} ${spacing[6]}`,
  marginXl: `${spacing[6]} ${spacing[8]}`,

  // Gap patterns
  gapXs: spacing[2],
  gapSm: spacing[3],
  gapMd: spacing[4],
  gapLg: spacing[6],
  gapXl: spacing[8],
} as const;

