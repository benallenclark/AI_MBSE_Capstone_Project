# Global Styling System

This directory contains the centralized styling constants and global styles for the application.

## Structure

### Files

- **`colors.ts`** - Color constants and palette
- **`typography.ts`** - Font families, sizes, weights, and predefined text styles
- **`spacing.ts`** - Spacing scale and common spacing patterns
- **`globals.css`** - Global CSS styles and CSS variables
- **`index.ts`** - Central export point for all style constants

## Usage

### Using TypeScript Constants

Import style constants directly in your TypeScript/React files:

```typescript
import { colors, typography, spacing } from '@/styles';

// Use in component styles
const buttonStyle = {
  color: colors.white,
  fontSize: typography.fontSize.lg,
  padding: `${spacing[2]} ${spacing[4]}`,
};
```

### Using CSS Variables

Use CSS variables in your CSS files:

```css
.my-component {
  color: var(--color-primary);
  font-size: var(--font-size-lg);
  padding: var(--spacing-md);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-md);
}
```

### Using Predefined Text Styles

Apply predefined typography styles:

```typescript
import { textStyles } from '@/styles';

const headingStyle = {
  ...textStyles.h1,
};

const bodyStyle = {
  ...textStyles.body,
};
```

## Color Palette

### Primary Colors
- `primary` - #646cff
- `primaryHover` - #535bf2
- `primaryLight` - #747bff

### Neutral Colors
- `white` - #ffffff
- `gray50` through `gray900` - Full grayscale range
- `black` - #000000

### Semantic Colors
- `success` - #22c55e
- `warning` - #f59e0b
- `error` - #ef4444
- `info` - #3b82f6

## Typography Scale

### Font Sizes
- `xs` - 0.75rem (12px)
- `sm` - 0.875rem (14px)
- `base` - 1rem (16px)
- `lg` - 1.125rem (18px)
- `xl` - 1.25rem (20px)
- `2xl` - 1.5rem (24px)
- `3xl` - 1.875rem (30px)
- `4xl` - 2.25rem (36px)
- `5xl` - 3rem (48px)
- `6xl` - 3.75rem (60px)

### Font Weights
- `thin` - 100
- `extralight` - 200
- `light` - 300
- `normal` - 400
- `medium` - 500
- `semibold` - 600
- `bold` - 700
- `extrabold` - 800
- `black` - 900

### Predefined Text Styles
- `h1` through `h6` - Heading styles
- `body` - Standard body text
- `bodySmall` - Smaller body text
- `caption` - Caption text
- `button` - Button text

## Spacing Scale

Base unit: 4px (0.25rem)

- `0` - 0
- `1` - 0.25rem (4px)
- `2` - 0.5rem (8px)
- `3` - 0.75rem (12px)
- `4` - 1rem (16px)
- `5` - 1.25rem (20px)
- `6` - 1.5rem (24px)
- `8` - 2rem (32px)
- `12` - 3rem (48px)
- `16` - 4rem (64px)
- `20` - 5rem (80px)
- `24` - 6rem (96px)
- ... and more

## CSS Variables

All style constants are also available as CSS variables in `globals.css`:

- Color variables: `--color-*`
- Typography variables: `--font-*`
- Spacing variables: `--spacing-*`
- Transition variables: `--transition-*`
- Border radius variables: `--radius-*`
- Shadow variables: `--shadow-*`
- Z-index variables: `--z-*`

## Dark Mode Support

The global styles include automatic dark mode support via `prefers-color-scheme` media query. Colors and backgrounds automatically adjust based on the user's system preference.

## Best Practices

1. **Use constants over magic numbers** - Always reference the style constants instead of hardcoding values
2. **Maintain consistency** - Use the predefined scales for colors, typography, and spacing
3. **Leverage CSS variables** - Use CSS variables in component styles for consistency
4. **Follow the scale** - Don't create new sizes outside the defined scale
5. **Use semantic colors** - Use `success`, `warning`, `error`, `info` for meaningful colors

