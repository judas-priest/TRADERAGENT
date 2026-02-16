export const theme = {
  colors: {
    background: '#0d1117',
    surface: '#161b22',
    surfaceHover: '#1c2128',
    border: '#30363d',
    text: '#e6edf3',
    textMuted: '#8b949e',
    primary: '#640075',
    primaryHover: '#7a008f',
    blue: '#007aff',
    orange: '#ed800d',
    profit: '#3fb950',
    loss: '#f85149',
  },
} as const;

export type ThemeColors = typeof theme.colors;
