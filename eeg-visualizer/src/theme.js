// src/theme.js
import { tailwind } from '@theme-ui/presets'

const theme = {
  ...tailwind,
  colors: {
    ...tailwind.colors,
    primary: '#0af',
    secondary: '#f06',
    background: '#0a0a0a',
    text: '#eee',
  },
  styles: {
    ...tailwind.styles,
    root: {
      backgroundColor: 'background',
      color: 'text',
      fontFamily: 'system-ui, sans-serif',
      lineHeight: '1.6',
    },
  },
}

export default theme
