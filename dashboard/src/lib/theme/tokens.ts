/**
 * Design Token Schema 定义
 * 集中管理所有设计令牌（颜色、排版、间距、阴影、动画等）
 */

// ============================================================================
// Color Tokens 类型定义
// ============================================================================

export type ColorTokens = {
  primary: string
  'primary-foreground': string
  'primary-gradient': string
  secondary: string
  'secondary-foreground': string
  muted: string
  'muted-foreground': string
  accent: string
  'accent-foreground': string
  destructive: string
  'destructive-foreground': string
  background: string
  foreground: string
  card: string
  'card-foreground': string
  popover: string
  'popover-foreground': string
  border: string
  input: string
  ring: string
  'chart-1': string
  'chart-2': string
  'chart-3': string
  'chart-4': string
  'chart-5': string
}

// ============================================================================
// Typography Tokens 类型定义
// ============================================================================

export type TypographyTokens = {
  'font-family-base': string
  'font-family-code': string
  'font-size-xs': string
  'font-size-sm': string
  'font-size-base': string
  'font-size-lg': string
  'font-size-xl': string
  'font-size-2xl': string
  'font-weight-normal': number
  'font-weight-medium': number
  'font-weight-semibold': number
  'font-weight-bold': number
  'line-height-tight': number
  'line-height-normal': number
  'line-height-relaxed': number
  'letter-spacing-tight': string
  'letter-spacing-normal': string
  'letter-spacing-wide': string
}

// ============================================================================
// Visual Tokens 类型定义
// ============================================================================

export type VisualTokens = {
  'radius-sm': string
  'radius-md': string
  'radius-lg': string
  'radius-xl': string
  'radius-full': string
  'shadow-sm': string
  'shadow-md': string
  'shadow-lg': string
  'shadow-xl': string
  'blur-sm': string
  'blur-md': string
  'blur-lg': string
  'opacity-disabled': number
  'opacity-hover': number
  'opacity-overlay': number
}

// ============================================================================
// Layout Tokens 类型定义
// ============================================================================

export type LayoutTokens = {
  'space-xs': string
  'space-sm': string
  'space-md': string
  'space-lg': string
  'space-xl': string
  'space-2xl': string
  'sidebar-width': string
  'sidebar-logo-height': string
  'sidebar-logo-padding-x': string
  'sidebar-nav-padding': string
  'sidebar-nav-padding-collapsed': string
  'sidebar-section-gap': string
  'sidebar-section-title-height': string
  'sidebar-section-title-margin-bottom': string
  'sidebar-section-title-margin-bottom-collapsed': string
  'sidebar-nav-item-gap': string
  'sidebar-collapsed-width': string
  'sidebar-nav-item-height': string
  'sidebar-nav-item-padding-x': string
  'sidebar-nav-item-collapsed-width': string
  'header-height': string
}

// ============================================================================
// Animation Tokens 类型定义
// ============================================================================

export type AnimationTokens = {
  'anim-duration-fast': string
  'anim-duration-normal': string
  'anim-duration-slow': string
  'anim-easing-default': string
  'anim-easing-in': string
  'anim-easing-out': string
  'anim-easing-in-out': string
  'transition-colors': string
  'transition-transform': string
  'transition-opacity': string
}

// ============================================================================
// Aggregated Theme Tokens
// ============================================================================

export type ThemeTokens = {
  color: ColorTokens
  typography: TypographyTokens
  visual: VisualTokens
  layout: LayoutTokens
  animation: AnimationTokens
}

// ============================================================================
// Theme Preset & Config Types
// ============================================================================

export type ThemePreset = {
  id: string
  name: string
  description: string
  tokens: ThemeTokens
  isDark: boolean
}

export type DashboardStyle = 'modern'

export const DASHBOARD_STYLES: readonly DashboardStyle[] = ['modern']

export type StyleTokenOverrides = Partial<Record<DashboardStyle, Partial<ThemeTokens>>>
export type StyleCustomCSS = Partial<Record<DashboardStyle, string>>
export type StyleBackgroundConfigMap = Partial<Record<DashboardStyle, BackgroundConfigMap>>

export const DEFAULT_DASHBOARD_STYLE: DashboardStyle = 'modern'

export type UserThemeConfig = {
  selectedPreset: string
  styleTokenOverrides: StyleTokenOverrides
  styleCustomCSS: StyleCustomCSS
  styleBackgroundConfig?: StyleBackgroundConfigMap
  dashboardStyle: DashboardStyle
}

// ============================================================================
// Default Light Tokens (from index.css :root)
// ============================================================================

export const defaultLightTokens: ThemeTokens = {
  color: {
    primary: '228 18% 13%',
    'primary-foreground': '0 0% 100%',
    'primary-gradient': 'none',
    secondary: '228 20% 94.5%',
    'secondary-foreground': '228 14% 22%',
    muted: '228 22% 95.5%',
    'muted-foreground': '228 9% 45%',
    accent: '228 20% 94%',
    'accent-foreground': '228 18% 13%',
    destructive: '0 84.2% 60.2%',
    'destructive-foreground': '210 40% 98%',
    background: '228 24% 96.5%',
    foreground: '228 18% 13%',
    card: '0 0% 100%',
    'card-foreground': '228 18% 13%',
    popover: '0 0% 100%',
    'popover-foreground': '228 18% 13%',
    border: '228 16% 90%',
    input: '228 14% 86.5%',
    ring: '221 83% 56%',
    'chart-1': '217 91% 53%',
    'chart-2': '189 94% 34%',
    'chart-3': '258 90% 60%',
    'chart-4': '322 81% 43%',
    'chart-5': '160 84% 32%',
  },
  typography: {
    'font-family-base':
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    'font-family-code': '"JetBrains Mono", "Monaco", "Courier New", monospace',
    'font-size-xs': '0.75rem',
    'font-size-sm': '0.875rem',
    'font-size-base': '1rem',
    'font-size-lg': '1.125rem',
    'font-size-xl': '1.25rem',
    'font-size-2xl': '1.5rem',
    'font-weight-normal': 400,
    'font-weight-medium': 500,
    'font-weight-semibold': 600,
    'font-weight-bold': 700,
    'line-height-tight': 1.2,
    'line-height-normal': 1.5,
    'line-height-relaxed': 1.75,
    'letter-spacing-tight': '-0.02em',
    'letter-spacing-normal': '0em',
    'letter-spacing-wide': '0.02em',
  },
  visual: {
    'radius-sm': '0.375rem',
    'radius-md': '0.625rem',
    'radius-lg': '1rem',
    'radius-xl': '1.5rem',
    'radius-full': '9999px',
    'shadow-sm': '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    'shadow-md': '0 4px 6px -1px rgba(0, 0, 0, 0.1)',
    'shadow-lg': '0 10px 15px -3px rgba(0, 0, 0, 0.1)',
    'shadow-xl': '0 20px 25px -5px rgba(0, 0, 0, 0.1)',
    'blur-sm': '4px',
    'blur-md': '12px',
    'blur-lg': '24px',
    'opacity-disabled': 0.5,
    'opacity-hover': 0.8,
    'opacity-overlay': 0.75,
  },
  layout: {
    'space-xs': '0.5rem',
    'space-sm': '0.75rem',
    'space-md': '1rem',
    'space-lg': '1.5rem',
    'space-xl': '2rem',
    'space-2xl': '3rem',
    'sidebar-width': '13rem',
    'sidebar-logo-height': '5rem',
    'sidebar-logo-padding-x': '1rem',
    'sidebar-nav-padding': '1rem',
    'sidebar-nav-padding-collapsed': '0.5rem',
    'sidebar-section-gap': '0.75rem',
    'sidebar-section-title-height': '1.25rem',
    'sidebar-section-title-margin-bottom': '0.5rem',
    'sidebar-section-title-margin-bottom-collapsed': '0.25rem',
    'sidebar-nav-item-gap': '0.25rem',
    'sidebar-collapsed-width': '4rem',
    'sidebar-nav-item-height': '2.5rem',
    'sidebar-nav-item-padding-x': '0.75rem',
    'sidebar-nav-item-collapsed-width': '3rem',
    'header-height': '3.5rem',
  },
  animation: {
    'anim-duration-fast': '150ms',
    'anim-duration-normal': '300ms',
    'anim-duration-slow': '500ms',
    'anim-easing-default': 'cubic-bezier(0.4, 0, 0.2, 1)',
    'anim-easing-in': 'cubic-bezier(0.4, 0, 1, 1)',
    'anim-easing-out': 'cubic-bezier(0, 0, 0.2, 1)',
    'anim-easing-in-out': 'cubic-bezier(0.4, 0, 0.2, 1)',
    'transition-colors': 'color 300ms cubic-bezier(0.4, 0, 0.2, 1)',
    'transition-transform': 'transform 300ms cubic-bezier(0.4, 0, 0.2, 1)',
    'transition-opacity': 'opacity 300ms cubic-bezier(0.4, 0, 0.2, 1)',
  },
}

// ============================================================================
// Default Dark Tokens (from index.css .dark)
// ============================================================================

export const defaultDarkTokens: ThemeTokens = {
  color: {
    primary: '228 20% 93%',
    'primary-foreground': '228 12% 10%',
    'primary-gradient': 'none',
    secondary: '228 9% 18%',
    'secondary-foreground': '228 15% 92%',
    muted: '228 9% 16%',
    'muted-foreground': '228 8% 64%',
    accent: '228 9% 19%',
    'accent-foreground': '228 20% 95%',
    destructive: '0 62.8% 30.6%',
    'destructive-foreground': '210 40% 98%',
    background: '228 12% 8.5%',
    foreground: '228 20% 95%',
    card: '228 10% 12.5%',
    'card-foreground': '228 20% 95%',
    popover: '228 10% 15%',
    'popover-foreground': '228 20% 95%',
    border: '228 8% 20%',
    input: '228 8% 24%',
    ring: '213 94% 68%',
    'chart-1': '213 94% 68%',
    'chart-2': '188 86% 60%',
    'chart-3': '255 96% 76%',
    'chart-4': '325 86% 72%',
    'chart-5': '158 70% 60%',
  },
  typography: {
    'font-family-base':
      '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    'font-family-code': '"JetBrains Mono", "Monaco", "Courier New", monospace',
    'font-size-xs': '0.75rem',
    'font-size-sm': '0.875rem',
    'font-size-base': '1rem',
    'font-size-lg': '1.125rem',
    'font-size-xl': '1.25rem',
    'font-size-2xl': '1.5rem',
    'font-weight-normal': 400,
    'font-weight-medium': 500,
    'font-weight-semibold': 600,
    'font-weight-bold': 700,
    'line-height-tight': 1.2,
    'line-height-normal': 1.5,
    'line-height-relaxed': 1.75,
    'letter-spacing-tight': '-0.02em',
    'letter-spacing-normal': '0em',
    'letter-spacing-wide': '0.02em',
  },
  visual: {
    'radius-sm': '0.375rem',
    'radius-md': '0.625rem',
    'radius-lg': '1rem',
    'radius-xl': '1.5rem',
    'radius-full': '9999px',
    'shadow-sm': '0 1px 2px 0 rgba(0, 0, 0, 0.25)',
    'shadow-md': '0 4px 6px -1px rgba(0, 0, 0, 0.3)',
    'shadow-lg': '0 10px 15px -3px rgba(0, 0, 0, 0.4)',
    'shadow-xl': '0 20px 25px -5px rgba(0, 0, 0, 0.5)',
    'blur-sm': '4px',
    'blur-md': '12px',
    'blur-lg': '24px',
    'opacity-disabled': 0.5,
    'opacity-hover': 0.8,
    'opacity-overlay': 0.75,
  },
  layout: {
    'space-xs': '0.5rem',
    'space-sm': '0.75rem',
    'space-md': '1rem',
    'space-lg': '1.5rem',
    'space-xl': '2rem',
    'space-2xl': '3rem',
    'sidebar-width': '13rem',
    'sidebar-logo-height': '5rem',
    'sidebar-logo-padding-x': '1rem',
    'sidebar-nav-padding': '1rem',
    'sidebar-nav-padding-collapsed': '0.5rem',
    'sidebar-section-gap': '0.75rem',
    'sidebar-section-title-height': '1.25rem',
    'sidebar-section-title-margin-bottom': '0.5rem',
    'sidebar-section-title-margin-bottom-collapsed': '0.25rem',
    'sidebar-nav-item-gap': '0.25rem',
    'sidebar-collapsed-width': '4rem',
    'sidebar-nav-item-height': '2.5rem',
    'sidebar-nav-item-padding-x': '0.75rem',
    'sidebar-nav-item-collapsed-width': '3rem',
    'header-height': '3.5rem',
  },
  animation: {
    'anim-duration-fast': '150ms',
    'anim-duration-normal': '300ms',
    'anim-duration-slow': '500ms',
    'anim-easing-default': 'cubic-bezier(0.4, 0, 0.2, 1)',
    'anim-easing-in': 'cubic-bezier(0.4, 0, 1, 1)',
    'anim-easing-out': 'cubic-bezier(0, 0, 0.2, 1)',
    'anim-easing-in-out': 'cubic-bezier(0.4, 0, 0.2, 1)',
    'transition-colors': 'color 300ms cubic-bezier(0.4, 0, 0.2, 1)',
    'transition-transform': 'transform 300ms cubic-bezier(0.4, 0, 0.2, 1)',
    'transition-opacity': 'opacity 300ms cubic-bezier(0.4, 0, 0.2, 1)',
  },
}

// ============================================================================
// Token Utility Functions
// ============================================================================

/**
 * 将 Token 类别和 key 转换为 CSS 变量名
 * @example tokenToCSSVarName('color', 'primary') => '--color-primary'
 */
export function tokenToCSSVarName(
  category: keyof ThemeTokens | 'color' | 'typography' | 'visual' | 'layout' | 'animation',
  key: string
): string {
  return `--${category}-${key}`
}

// ============================================================================
// Background Config Types
// ============================================================================

export type BackgroundEffects = {
  blur: number // px, 0-50
  overlayColor: string // HSL string，如 '0 0% 0%'
  overlayOpacity: number // 0-1
  position: 'cover' | 'contain' | 'center' | 'stretch'
  brightness: number // 0-200, default 100
  contrast: number // 0-200, default 100
  saturate: number // 0-200, default 100
  gradientOverlay?: string // CSS gradient string（可选）
}

export type BackgroundConfig = {
  type: 'none' | 'image' | 'video'
  assetId?: string // IndexedDB asset ID
  inherit?: boolean // true = 继承页面背景
  effects: BackgroundEffects
  customCSS: string // 组件级自定义 CSS
}

export type BackgroundConfigMap = {
  page?: BackgroundConfig
  sidebar?: BackgroundConfig
  header?: BackgroundConfig
  card?: BackgroundConfig
  dialog?: BackgroundConfig
}

export const defaultBackgroundEffects: BackgroundEffects = {
  blur: 0,
  overlayColor: '0 0% 0%',
  overlayOpacity: 0,
  position: 'cover',
  brightness: 100,
  contrast: 100,
  saturate: 100,
}

export const defaultBackgroundConfig: BackgroundConfig = {
  type: 'none',
  effects: defaultBackgroundEffects,
  customCSS: '',
}
