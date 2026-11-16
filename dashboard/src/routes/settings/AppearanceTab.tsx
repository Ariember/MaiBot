import { Card } from '@/components/ui/card'
import { useState, useMemo, useRef, useCallback, useEffect } from 'react'

import {
  AlertTriangle,
  Download,
  Monitor,
  Moon,
  RotateCcw,
  Sun,
  Trash2,
  Upload,
} from 'lucide-react'

import { useAnimation } from '@/hooks/use-animation'
import { useTheme } from '@/components/use-theme'
import { useToast } from '@/hooks/use-toast'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Switch } from '@/components/ui/switch'
import { Slider } from '@/components/ui/slider'
import { getComputedTokens } from '@/lib/theme/pipeline'
import {
  defaultBackgroundConfig,
  defaultBackgroundEffects,
  defaultLightTokens,
} from '@/lib/theme/tokens'
import { exportThemeJSON, importThemeJSON } from '@/lib/theme/storage'
import type {
  BackgroundConfigMap,
  BackgroundEffects,
  ThemeTokens,
  TypographyTokens,
} from '@/lib/theme/tokens'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { CodeEditor } from '@/components/CodeEditor'
import { BackgroundEffectsControls } from '@/components/background-effects-controls'
import { BackgroundUploader } from '@/components/background-uploader'
import { ComponentCSSEditor } from '@/components/component-css-editor'
import { sanitizeCSS } from '@/lib/theme/sanitizer'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { SegmentedControl } from '@/components/ui/management'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'

type ThemeMode = 'light' | 'dark' | 'system'

const themeModeOptions: Array<{
  value: ThemeMode
  label: string
  description: string
  icon: typeof Monitor
}> = [
  {
    value: 'light',
    label: "浅色",
    description: "始终使用浅色主题",
    icon: Sun,
  },
  {
    value: 'dark',
    label: "深色",
    description: "始终使用深色主题",
    icon: Moon,
  },
  {
    value: 'system',
    label: "跟随系统",
    description: "根据系统设置自动切换",
    icon: Monitor,
  },
]

/**
 * 安全访问当前风格 token 覆盖中的子属性值
 * @param overrides - Partial<ThemeTokens>
 * @param section - 如 'typography', 'visual', 'layout', 'animation'
 * @param key - token 键名，如 'font-family-base'
 * @param defaultValue - 默认值
 */
function getTokenValue<T>(
  overrides: Partial<ThemeTokens> | undefined,
  section: keyof ThemeTokens,
  key: string,
  defaultValue: T
): T {
  if (!overrides || !overrides[section]) return defaultValue
  const sectionTokens = overrides[section] as Record<string, unknown> | undefined
  if (!sectionTokens || !(key in sectionTokens)) return defaultValue
  return (sectionTokens[key] ?? defaultValue) as T
}

function buildFontSizeTokens(
  basePx: number
): Pick<
  TypographyTokens,
  | 'font-size-xs'
  | 'font-size-sm'
  | 'font-size-base'
  | 'font-size-lg'
  | 'font-size-xl'
  | 'font-size-2xl'
> {
  const toRem = (px: number) => `${Number((px / 16).toFixed(4))}rem`

  return {
    'font-size-xs': toRem(basePx * 0.75),
    'font-size-sm': toRem(basePx * 0.875),
    'font-size-base': toRem(basePx),
    'font-size-lg': toRem(basePx * 1.125),
    'font-size-xl': toRem(basePx * 1.25),
    'font-size-2xl': toRem(basePx * 1.5),
  }
}
export function AppearanceTab() {
  const { theme, setTheme, themeConfig, updateThemeConfig, resolvedTheme, resetTheme } = useTheme()
  const { enableAnimations, setEnableAnimations } = useAnimation()
  const { toast } = useToast()
  const dashboardStyle = themeConfig.dashboardStyle
  const activeCustomCSS = themeConfig.styleCustomCSS?.[dashboardStyle] ?? ''
  const activeBackgroundConfig = useMemo(
    () => themeConfig.styleBackgroundConfig?.[dashboardStyle] ?? {},
    [dashboardStyle, themeConfig.styleBackgroundConfig]
  )

  const [localCSS, setLocalCSS] = useState(activeCustomCSS)
  const [bgDraftConfig, setBgDraftConfig] = useState<BackgroundConfigMap>(activeBackgroundConfig)
  const [cssWarnings, setCssWarnings] = useState<string[]>([])
  const cssDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const bgDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const defaultSidebarWidthRem = 13
  const activeTokenOverrides = useMemo(
    () => themeConfig.styleTokenOverrides?.[themeConfig.dashboardStyle] ?? {},
    [themeConfig.dashboardStyle, themeConfig.styleTokenOverrides]
  )

  const updateTokenSection = useCallback(
    <K extends keyof ThemeTokens>(section: K, partial: Partial<ThemeTokens[K]>) => {
      const nextStyleOverrides = {
        ...activeTokenOverrides,
        [section]: {
          ...activeTokenOverrides[section],
          ...partial,
        } as ThemeTokens[K],
      }

      updateThemeConfig({
        styleTokenOverrides: {
          ...themeConfig.styleTokenOverrides,
          [themeConfig.dashboardStyle]: nextStyleOverrides,
        },
      })
    },
    [
      activeTokenOverrides,
      themeConfig.dashboardStyle,
      themeConfig.styleTokenOverrides,
      updateThemeConfig,
    ]
  )

  const resetTokenSection = useCallback(
    (section: keyof ThemeTokens) => {
      const newOverrides: Partial<ThemeTokens> = { ...activeTokenOverrides }
      delete newOverrides[section]
      updateThemeConfig({
        styleTokenOverrides: {
          ...themeConfig.styleTokenOverrides,
          [themeConfig.dashboardStyle]: newOverrides,
        },
      })
    },
    [
      activeTokenOverrides,
      themeConfig.dashboardStyle,
      themeConfig.styleTokenOverrides,
      updateThemeConfig,
    ]
  )

  const handleCSSChange = useCallback(
    (val: string) => {
      setLocalCSS(val)
      const result = sanitizeCSS(val)
      setCssWarnings(result.warnings)

      if (cssDebounceRef.current) clearTimeout(cssDebounceRef.current)
      cssDebounceRef.current = setTimeout(() => {
        updateThemeConfig({
          styleCustomCSS: {
            ...themeConfig.styleCustomCSS,
            [dashboardStyle]: val,
          },
        })
      }, 500)
    },
    [dashboardStyle, themeConfig.styleCustomCSS, updateThemeConfig]
  )

  useEffect(() => {
    setBgDraftConfig(activeBackgroundConfig)
  }, [activeBackgroundConfig])

  useEffect(() => {
    setLocalCSS(activeCustomCSS)
    setCssWarnings(sanitizeCSS(activeCustomCSS).warnings)
  }, [activeCustomCSS])

  useEffect(() => {
    return () => {
      if (cssDebounceRef.current) clearTimeout(cssDebounceRef.current)
      if (bgDebounceRef.current) clearTimeout(bgDebounceRef.current)
    }
  }, [])

  const handleExport = () => {
    const json = exportThemeJSON()
    const blob = new Blob([json], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `maibot-theme-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      const json = ev.target?.result as string
      const result = importThemeJSON(json)
      if (result.success) {
        // 导入成功后需要刷新页面使配置生效（因为 ThemeProvider 需要重新读取 localStorage）
        toast({
          title: '导入成功',
          description: '主题配置已导入，页面将自动刷新',
        })
        setTimeout(() => window.location.reload(), 1000)
      } else {
        toast({
          title: '导入失败',
          description: result.errors.join('; '),
          variant: 'destructive',
        })
      }
    }
    reader.readAsText(file)
    // 重置 input，允许重复选择同一文件
    e.target.value = ''
  }

  const handleResetTheme = () => {
    resetTheme()
    setLocalCSS('')
    setCssWarnings([])
    toast({
      title: '重置成功',
      description: '主题已重置为默认值',
    })
  }

  const computedTokens = useMemo(() => {
    return getComputedTokens(themeConfig, resolvedTheme === 'dark')
  }, [themeConfig, resolvedTheme])
  const baseFontSizePx =
    parseFloat(
      getTokenValue(
        activeTokenOverrides,
        'typography',
        'font-size-base',
        computedTokens.typography['font-size-base']
      )
    ) * 16

  const bgConfig: BackgroundConfigMap = bgDraftConfig

  const scheduleBackgroundConfigPersist = useCallback(
    (nextConfig: BackgroundConfigMap) => {
      if (bgDebounceRef.current) clearTimeout(bgDebounceRef.current)
      bgDebounceRef.current = setTimeout(() => {
        updateThemeConfig({
          styleBackgroundConfig: {
            ...themeConfig.styleBackgroundConfig,
            [dashboardStyle]: nextConfig,
          },
        })
      }, 180)
    },
    [dashboardStyle, themeConfig.styleBackgroundConfig, updateThemeConfig]
  )

  const handleBgAssetChange = (layerId: keyof BackgroundConfigMap, assetId: string | undefined) => {
    const current = bgConfig[layerId] ?? defaultBackgroundConfig
    const newMap: BackgroundConfigMap = {
      ...bgConfig,
      [layerId]: { ...current, assetId, type: assetId ? 'image' : 'none' },
    }
    setBgDraftConfig(newMap)
    scheduleBackgroundConfigPersist(newMap)
  }

  const handleBgEffectsChange = (
    layerId: keyof BackgroundConfigMap,
    effects: BackgroundEffects
  ) => {
    const current = bgConfig[layerId] ?? defaultBackgroundConfig
    const newMap: BackgroundConfigMap = { ...bgConfig, [layerId]: { ...current, effects } }
    setBgDraftConfig(newMap)
    scheduleBackgroundConfigPersist(newMap)
  }

  const handleBgCSSChange = (layerId: keyof BackgroundConfigMap, css: string) => {
    const current = bgConfig[layerId] ?? defaultBackgroundConfig
    const newMap: BackgroundConfigMap = { ...bgConfig, [layerId]: { ...current, customCSS: css } }
    setBgDraftConfig(newMap)
    scheduleBackgroundConfigPersist(newMap)
  }

  const handleBgInheritChange = (layerId: keyof BackgroundConfigMap, inherit: boolean) => {
    const current = bgConfig[layerId] ?? defaultBackgroundConfig
    const newMap: BackgroundConfigMap = { ...bgConfig, [layerId]: { ...current, inherit } }
    setBgDraftConfig(newMap)
    scheduleBackgroundConfigPersist(newMap)
  }

  return (
    <div className="space-y-6 sm:space-y-8">
      {/* 主题模式 */}
      <div>
        <h3 className="mb-3 text-base font-semibold sm:mb-4 sm:text-lg">
          {'主题模式'}
        </h3>
        <SegmentedControl
          aria-label={'主题模式'}
          value={theme}
          onValueChange={(value) => {
            const option = themeModeOptions.find((item) => item.value === value)
            if (option) setTheme(option.value)
          }}
          options={themeModeOptions.map((option) => {
            const Icon = option.icon
            return {
              value: option.value,
              label: <span className="inline-flex items-center gap-2" title={option.description}><Icon />{option.label}</span>,
            }
          })}
        />
      </div>

      {/* 样式微调 */}
      <div>
        <h3 className="mb-3 text-base font-semibold sm:mb-4 sm:text-lg">
          {'界面样式微调'}
        </h3>

        <Accordion type="single" collapsible className="w-full">
          {/* 1. 字体排版 (Typography) */}
          <AccordionItem value="typography">
            <AccordionTrigger>{'字体排版 (Typography)'}</AccordionTrigger>
            <AccordionContent>
              <div className="space-y-4 pt-2">
                <div className="flex justify-end">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => resetTokenSection('typography')}
                    disabled={!activeTokenOverrides?.typography}
                    className="h-8 text-xs"
                  >
                    <RotateCcw className="mr-2 h-3.5 w-3.5" />
                    {'重置默认'}
                  </Button>
                </div>

                <div className="space-y-2">
                  <Label>{'字体族 (Font Family)'}</Label>
                  <Select
                    value={(() => {
                      const fontFamily = getTokenValue(
                        activeTokenOverrides,
                        'typography',
                        'font-family-base',
                        computedTokens.typography['font-family-base']
                      )
                      if (fontFamily.includes('ui-serif')) return 'serif'
                      if (fontFamily.includes('ui-monospace')) return 'mono'
                      if (fontFamily) return 'sans'
                      return 'system'
                    })()}
                    onValueChange={(val) => {
                      let fontVal = defaultLightTokens.typography['font-family-base']
                      if (val === 'serif')
                        fontVal = 'ui-serif, Georgia, Cambria, "Times New Roman", Times, serif'
                      else if (val === 'mono')
                        fontVal =
                          'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace'
                      else if (val === 'sans')
                        fontVal =
                          'ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'

                      updateTokenSection('typography', {
                        'font-family-base': fontVal,
                      })
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue
                        placeholder={'选择字体族'}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="system">
                        {'系统默认 (System)'}
                      </SelectItem>
                      <SelectItem value="sans">
                        {'无衬线 (Sans-serif)'}
                      </SelectItem>
                      <SelectItem value="serif">
                        {'衬线 (Serif)'}
                      </SelectItem>
                      <SelectItem value="mono">
                        {'等宽 (Monospace)'}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-4">
                  <div className="flex justify-between">
                    <Label>{'基准字体大小 (Base Size)'}</Label>
                    <span className="text-muted-foreground text-sm">{baseFontSizePx}px</span>
                  </div>
                  <Slider
                    defaultValue={[16]}
                    value={[baseFontSizePx]}
                    min={12}
                    max={20}
                    step={1}
                    onValueChange={(vals) => {
                      updateTokenSection('typography', {
                        ...buildFontSizeTokens(vals[0]),
                      })
                    }}
                  />
                </div>

                <div className="space-y-2">
                  <Label>{'行高 (Line Height)'}</Label>
                  <Select
                    value={String(
                      getTokenValue(
                        activeTokenOverrides,
                        'typography',
                        'line-height-normal',
                        computedTokens.typography['line-height-normal']
                      )
                    )}
                    onValueChange={(val) => {
                      updateTokenSection('typography', {
                        'line-height-normal': parseFloat(val),
                      })
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue
                        placeholder={'选择行高'}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="1.2">
                        {'紧凑 (1.2)'}
                      </SelectItem>
                      <SelectItem value="1.5">
                        {'正常 (1.5)'}
                      </SelectItem>
                      <SelectItem value="1.75">
                        {'宽松 (1.75)'}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* 2. 视觉效果 (Visual) */}
          <AccordionItem value="visual">
            <AccordionTrigger>{'视觉效果 (Visual)'}</AccordionTrigger>
            <AccordionContent>
              <div className="space-y-4 pt-2">
                <div className="flex justify-end">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => resetTokenSection('visual')}
                    disabled={!activeTokenOverrides?.visual}
                    className="h-8 text-xs"
                  >
                    <RotateCcw className="mr-2 h-3.5 w-3.5" />
                    {'重置默认'}
                  </Button>
                </div>

                <div className="space-y-4">
                  <div className="flex justify-between">
                    <Label>{'圆角大小 (Radius)'}</Label>
                    <span className="text-muted-foreground text-sm">
                      {Math.round(
                        parseFloat(
                          getTokenValue(
                            activeTokenOverrides,
                            'visual',
                            'radius-md',
                            computedTokens.visual['radius-md']
                          )
                        ) * 16
                      )}
                      px
                    </span>
                  </div>
                  <Slider
                    defaultValue={[10]}
                    value={[
                      Math.round(
                        parseFloat(
                          getTokenValue(
                            activeTokenOverrides,
                            'visual',
                            'radius-md',
                            computedTokens.visual['radius-md']
                          )
                        ) * 16
                      ),
                    ]}
                    min={0}
                    max={24}
                    step={1}
                    onValueChange={(vals) => {
                      updateTokenSection('visual', {
                        'radius-sm': `${(vals[0] * 0.6) / 16}rem`,
                        'radius-md': `${vals[0] / 16}rem`,
                        'radius-lg': `${(vals[0] * 1.6) / 16}rem`,
                        'radius-xl': `${(vals[0] * 2.4) / 16}rem`,
                      })
                    }}
                  />
                </div>

                <div className="space-y-2">
                  <Label>{'阴影强度 (Shadow)'}</Label>
                  <Select
                    value={(() => {
                      const shadowMd = String(
                        getTokenValue(
                          activeTokenOverrides,
                          'visual',
                          'shadow-md',
                          computedTokens.visual['shadow-md']
                        )
                      )
                      if (shadowMd === 'none') return 'none'
                      if (shadowMd === defaultLightTokens.visual['shadow-sm']) return 'sm'
                      if (shadowMd === defaultLightTokens.visual['shadow-lg']) return 'lg'
                      if (shadowMd === defaultLightTokens.visual['shadow-xl']) return 'xl'
                      return 'md'
                    })()}
                    onValueChange={(val) => {
                      let shadowVal = defaultLightTokens.visual['shadow-md']
                      if (val === 'none') shadowVal = 'none'
                      else if (val === 'sm') shadowVal = defaultLightTokens.visual['shadow-sm']
                      else if (val === 'lg') shadowVal = defaultLightTokens.visual['shadow-lg']
                      else if (val === 'xl') shadowVal = defaultLightTokens.visual['shadow-xl']

                      updateTokenSection('visual', {
                        'shadow-md': shadowVal,
                      })
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder={'选择阴影强度'} />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">
                        {'无阴影 (None)'}
                      </SelectItem>
                      <SelectItem value="sm">{'轻微 (Small)'}</SelectItem>
                      <SelectItem value="md">{'中等 (Medium)'}</SelectItem>
                      <SelectItem value="lg">{'强烈 (Large)'}</SelectItem>
                      <SelectItem value="xl">{'极强 (Extra Large)'}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center justify-between">
                  <Label htmlFor="blur-switch">{'模糊效果 (Blur)'}</Label>
                  <Switch
                    id="blur-switch"
                    checked={
                      getTokenValue(
                        activeTokenOverrides,
                        'visual',
                        'blur-md',
                        computedTokens.visual['blur-md']
                      ) !== '0px'
                    }
                    onCheckedChange={(checked) => {
                      updateTokenSection('visual', {
                        'blur-md': checked ? defaultLightTokens.visual['blur-md'] : '0px',
                      })
                    }}
                  />
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* 3. 布局 (Layout) */}
          <AccordionItem value="layout">
            <AccordionTrigger>{'布局 (Layout)'}</AccordionTrigger>
            <AccordionContent>
              <div className="space-y-4 pt-2">
                <div className="flex justify-end">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => resetTokenSection('layout')}
                    disabled={!activeTokenOverrides?.layout}
                    className="h-8 text-xs"
                  >
                    <RotateCcw className="mr-2 h-3.5 w-3.5" />
                    {'重置默认'}
                  </Button>
                </div>

                <div className="space-y-4">
                  <div className="flex justify-between">
                    <Label>{'侧边栏宽度 (Sidebar Width)'}</Label>
                    <span className="text-muted-foreground text-sm">
                      {getTokenValue(
                        activeTokenOverrides,
                        'layout',
                        'sidebar-width',
                        computedTokens.layout['sidebar-width']
                      )}
                    </span>
                  </div>
                  <Slider
                    defaultValue={[defaultSidebarWidthRem]}
                    value={[
                      parseFloat(
                        getTokenValue(
                          activeTokenOverrides,
                          'layout',
                          'sidebar-width',
                          computedTokens.layout['sidebar-width']
                        )
                      ),
                    ]}
                    min={8}
                    max={24}
                    step={0.5}
                    onValueChange={(vals) => {
                      updateTokenSection('layout', {
                        'sidebar-width': `${vals[0]}rem`,
                      })
                    }}
                  />
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* 4. 动画 (Animation) */}
          <AccordionItem value="animation">
            <AccordionTrigger>{'动画 (Animation)'}</AccordionTrigger>
            <AccordionContent>
              <div className="space-y-4 pt-2">
                <div className="flex justify-end">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => resetTokenSection('animation')}
                    disabled={!activeTokenOverrides?.animation}
                    className="h-8 text-xs"
                  >
                    <RotateCcw className="mr-2 h-3.5 w-3.5" />
                    {'重置默认'}
                  </Button>
                </div>

                <div className="space-y-2">
                  <Label>{'动画速度 (Speed)'}</Label>
                  <Select
                    value={(() => {
                      const duration = String(
                        getTokenValue(
                          activeTokenOverrides,
                          'animation',
                          'anim-duration-normal',
                          computedTokens.animation['anim-duration-normal']
                        )
                      )
                      if (duration === '100ms') return 'fast'
                      if (duration === '500ms') return 'slow'
                      if (duration === '0ms') return 'off'
                      return 'normal'
                    })()}
                    onValueChange={(val) => {
                      let duration = '300ms'
                      if (val === 'fast') duration = '100ms'
                      else if (val === 'slow') duration = '500ms'
                      else if (val === 'off') duration = '0ms'

                      // 如果用户选了关闭，我们也应该同步更新 enableAnimations 开关
                      if (val === 'off' && enableAnimations) {
                        setEnableAnimations(false)
                      } else if (val !== 'off' && !enableAnimations) {
                        setEnableAnimations(true)
                      }

                      updateTokenSection('animation', {
                        'anim-duration-normal': duration,
                      })
                    }}
                  >
                    <SelectTrigger>
                      <SelectValue
                        placeholder={'选择动画速度'}
                      />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="fast">
                        {'快速 (100ms)'}
                      </SelectItem>
                      <SelectItem value="normal">
                        {'正常 (300ms)'}
                      </SelectItem>
                      <SelectItem value="slow">
                        {'慢速 (500ms)'}
                      </SelectItem>
                      <SelectItem value="off">
                        {'关闭 (0ms)'}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>

          {/* 5. 背景设置 (Backgrounds) */}
          <AccordionItem value="backgrounds">
            <AccordionTrigger>{'背景设置 (Backgrounds)'}</AccordionTrigger>
            <AccordionContent>
              <div className="pt-2">
                <Tabs defaultValue="page">
                  <TabsList className="grid w-full grid-cols-5">
                    <TabsTrigger value="page">{'页面'}</TabsTrigger>
                    <TabsTrigger value="sidebar">
                      {'侧边栏'}
                    </TabsTrigger>
                    <TabsTrigger value="header">Header</TabsTrigger>
                    <TabsTrigger value="card">Card</TabsTrigger>
                    <TabsTrigger value="dialog">Dialog</TabsTrigger>
                  </TabsList>

                  {(['page', 'sidebar', 'header', 'card', 'dialog'] as const).map((layerId) => (
                    <TabsContent key={layerId} value={layerId} className="mt-4 space-y-4">
                      {(() => {
                        const isInheritedLayer =
                          (layerId === 'sidebar' || layerId === 'header') &&
                          (bgConfig[layerId]?.inherit ?? false)

                        return (
                          <>
                            {layerId !== 'page' && (
                              <div className="bg-muted/30 flex items-center justify-between rounded-lg border px-4 py-3">
                                <div className="space-y-0.5">
                                  <Label className="text-sm font-medium">
                                    {'继承上级背景'}
                                  </Label>
                                  <p className="text-muted-foreground text-xs">
                                    {'开启后将使用上级层级的背景配置'}
                                  </p>
                                </div>
                                <Switch
                                  checked={bgConfig[layerId]?.inherit ?? false}
                                  onCheckedChange={(v) => handleBgInheritChange(layerId, v)}
                                />
                              </div>
                            )}
                            {isInheritedLayer && (
                              <div className="bg-muted/30 text-muted-foreground rounded-lg border px-4 py-3 text-sm">
                                该层当前直接继承界面背景，下面的资源、效果和 CSS 调节已禁用。
                              </div>
                            )}
                            <BackgroundUploader
                              assetId={bgConfig[layerId]?.assetId}
                              onAssetSelect={(id) => handleBgAssetChange(layerId, id)}
                              disabled={isInheritedLayer}
                            />
                            <BackgroundEffectsControls
                              effects={bgConfig[layerId]?.effects ?? defaultBackgroundEffects}
                              onChange={(effects) => handleBgEffectsChange(layerId, effects)}
                              disabled={isInheritedLayer}
                            />
                            <ComponentCSSEditor
                              componentId={layerId}
                              value={bgConfig[layerId]?.customCSS ?? ''}
                              onChange={(css) => handleBgCSSChange(layerId, css)}
                              disabled={isInheritedLayer}
                            />
                          </>
                        )
                      })()}
                    </TabsContent>
                  ))}
                </Tabs>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between sm:mb-4">
          <div>
            <h3 className="text-base font-semibold sm:text-lg">
              {'自定义 CSS'}
            </h3>
            <p className="text-muted-foreground mt-1 text-sm">
              {'编写自定义 CSS 来进一步个性化界面。危险的 CSS（如 @import、url()）将被自动过滤。'}
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setLocalCSS('')
              updateThemeConfig({
                styleCustomCSS: {
                  ...themeConfig.styleCustomCSS,
                  [dashboardStyle]: '',
                },
              })
              setCssWarnings([])
            }}
            disabled={!activeCustomCSS}
          >
            <Trash2 className="mr-1 h-4 w-4" />
            {'清除'}
          </Button>
        </div>

        <Card className="space-y-3 p-3 sm:p-4">
          <CodeEditor
            value={localCSS}
            language="css"
            height="250px"
            placeholder={'/* 在这里输入自定义 CSS */\n\n/* 例如: */\n/* .sidebar { background: #1a1a2e; } */'}
            onChange={handleCSSChange}
          />

          {cssWarnings.length > 0 && (
            <div className="rounded-md border border-yellow-200 bg-yellow-50 p-3 dark:border-yellow-800 dark:bg-yellow-950/30">
              <div className="mb-1 flex items-center gap-2 text-sm font-medium text-yellow-800 dark:text-yellow-200">
                <AlertTriangle className="h-4 w-4" />
                {'以下内容已被安全过滤：'}
              </div>
              <ul className="ml-6 list-disc space-y-0.5 text-xs text-yellow-700 dark:text-yellow-300">
                {cssWarnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      </div>

      {/* 动效设置 */}
      <div>
        <h3 className="mb-3 text-base font-semibold sm:mb-4 sm:text-lg">
          {'动画效果'}
        </h3>
        <div className="space-y-2 sm:space-y-3">
          {/* 全局动画开关 */}
          <Card className="p-3 sm:p-4">
            <div className="flex items-center justify-between">
              <div className="flex-1 space-y-0.5">
                <Label htmlFor="animations" className="cursor-pointer text-base font-medium">
                  {'启用动画效果'}
                </Label>
                <p className="text-muted-foreground text-sm">
                  {'关闭后将禁用所有过渡动画和特效，提升性能'}
                </p>
              </div>
              <Switch
                id="animations"
                checked={enableAnimations}
                onCheckedChange={setEnableAnimations}
              />
            </div>
          </Card>
        </div>
      </div>

      {/* 主题导入/导出 */}
      <div>
        <h3 className="mb-3 text-base font-semibold sm:mb-4 sm:text-lg">
          {'主题导入/导出'}
        </h3>
        <Card className="space-y-3 p-3 sm:p-4">
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
            {/* 导出按钮 */}
            <Button onClick={handleExport} variant="outline" className="gap-2">
              <Download className="h-4 w-4" />
              {'导出主题'}
            </Button>

            {/* 导入按钮 */}
            <Button
              onClick={() => fileInputRef.current?.click()}
              variant="outline"
              className="gap-2"
            >
              <Upload className="h-4 w-4" />
              {'导入主题'}
            </Button>

            {/* 重置按钮 */}
            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button variant="outline" className="gap-2">
                  <RotateCcw className="h-4 w-4" />
                  {'重置为默认'}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>
                    {'确认重置主题'}
                  </AlertDialogTitle>
                  <AlertDialogDescription>
                    {'这将重置所有主题设置为默认值，包括颜色、字体、布局和自定义 CSS。此操作不可撤销，确定要继续吗？'}
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>{'取消'}</AlertDialogCancel>
                  <AlertDialogAction onClick={handleResetTheme}>
                    {'确认重置'}
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>

          {/* 隐藏的文件输入 */}
          <input
            ref={fileInputRef}
            type="file"
            accept=".json"
            onChange={handleImport}
            className="hidden"
          />

          <p className="text-muted-foreground text-xs">{'导出主题为 JSON 文件便于分享或备份，导入时会自动应用所有配置。'}</p>
        </Card>
      </div>
    </div>
  )
}
