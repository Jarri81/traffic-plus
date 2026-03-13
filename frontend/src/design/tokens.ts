export const colors = {
  bg: { deepest: '#0B0F14', surface: '#111820', card: '#1A2230', elevated: '#232E3F' },
  text: { primary: '#F4F5F7', secondary: '#9BA3B0', muted: '#5E6A7A' },
  accent: { primary: '#D4915E', secondary: '#4EA8A6' },
  risk: { critical: '#E85D5D', high: '#E8A44C', medium: '#D4C24E', low: '#4EA86A' },
  border: { subtle: '#1E2A3A', hover: '#2A3A4E' },
  glass: 'rgba(17, 24, 32, 0.7)',
} as const;

export const chartColors = {
  primary: '#D4915E', secondary: '#4EA8A6',
  critical: '#E85D5D', high: '#E8A44C', medium: '#D4C24E', low: '#4EA86A',
  muted: '#5E6A7A', grid: '#1E2A3A', text: '#9BA3B0',
} as const;

export const spacing = {
  xs: '4px', sm: '8px', md: '16px', lg: '24px', xl: '32px', '2xl': '48px', '3xl': '64px',
} as const;

export const typography = {
  sizes: { xs: '11px', sm: '13px', base: '15px', lg: '18px', xl: '22px', '2xl': '28px', '4xl': '40px' },
  weights: { body: 400, label: 500, heading: 600, hero: 700 },
  letterSpacing: { heading: '-0.02em', label: '0.01em', body: 'normal' },
} as const;