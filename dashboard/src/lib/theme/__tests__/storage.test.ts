/**
 * theme/storage 单元测试：验证主题配置在 localStorage 中的
 * 读取归一化、保存、部分更新、导入导出与重置。
 */
import { beforeEach, describe, expect, it } from 'vitest'

import {
  THEME_STORAGE_KEYS,
  exportThemeJSON,
  importThemeJSON,
  loadThemeConfig,
  resetThemeToDefault,
  saveThemeConfig,
  saveThemePartial,
} from '../storage'
import type { UserThemeConfig } from '../tokens'

/** 构造一份合法的完整主题配置，按需覆盖字段 */
const buildConfig = (overrides: Partial<UserThemeConfig> = {}): UserThemeConfig => ({
  selectedPreset: 'light',
  styleTokenOverrides: {},
  styleCustomCSS: {},
  styleBackgroundConfig: {},
  dashboardStyle: 'modern',
  ...overrides,
})

beforeEach(() => {
  localStorage.clear()
})

describe('loadThemeConfig', () => {
  it('存储为空时返回默认配置', () => {
    expect(loadThemeConfig()).toEqual({
      selectedPreset: 'light',
      styleTokenOverrides: {},
      styleCustomCSS: {},
      styleBackgroundConfig: {},
      dashboardStyle: 'modern',
    })
  })

  it('读取已存值并逐字段归一化', () => {
    localStorage.setItem(THEME_STORAGE_KEYS.PRESET, 'ocean')
    localStorage.setItem(THEME_STORAGE_KEYS.DASHBOARD_STYLE, 'modern')
    // 未知风格 key（bogus）应被丢弃
    localStorage.setItem(
      THEME_STORAGE_KEYS.STYLE_OVERRIDES,
      JSON.stringify({
        modern: { color: { primary: '1 2% 3%' } },
        bogus: { color: { primary: '9 9% 9%' } },
      })
    )
    // 自定义 CSS 只保留 modern 风格
    localStorage.setItem(
      THEME_STORAGE_KEYS.STYLE_CUSTOM_CSS,
      JSON.stringify({ modern: '.a { color: red; }', 'future-retro': '.b {}' })
    )
    localStorage.setItem(
      THEME_STORAGE_KEYS.STYLE_BACKGROUND_CONFIG,
      JSON.stringify({ modern: { card: { type: 'none' } }, junk: 1 })
    )

    const config = loadThemeConfig()

    expect(config.selectedPreset).toBe('ocean')
    expect(config.dashboardStyle).toBe('modern')
    expect(config.styleTokenOverrides).toEqual({ modern: { color: { primary: '1 2% 3%' } } })
    expect(config.styleCustomCSS).toEqual({ modern: '.a { color: red; }' })
    expect(config.styleBackgroundConfig).toEqual({ modern: { card: { type: 'none' } } })
  })

  it('JSON 字段损坏时对应字段回退为默认值', () => {
    localStorage.setItem(THEME_STORAGE_KEYS.STYLE_OVERRIDES, '{broken')
    localStorage.setItem(THEME_STORAGE_KEYS.STYLE_CUSTOM_CSS, 'not-json')
    localStorage.setItem(THEME_STORAGE_KEYS.STYLE_BACKGROUND_CONFIG, '[')

    const config = loadThemeConfig()

    expect(config.styleTokenOverrides).toEqual({})
    expect(config.styleCustomCSS).toEqual({})
    expect(config.styleBackgroundConfig).toEqual({})
  })

  it.each(['future-retro', 'neon', 'millennium'])('无效或已移除的风格 %s 回退默认值', (style) => {
    localStorage.setItem(THEME_STORAGE_KEYS.DASHBOARD_STYLE, style)

    const config = loadThemeConfig()

    expect(config.dashboardStyle).toBe('modern')
  })

  it('已移除皮肤的缓存不会覆盖原版配置', () => {
    localStorage.setItem(THEME_STORAGE_KEYS.DASHBOARD_STYLE, 'future-retro')
    localStorage.setItem(
      THEME_STORAGE_KEYS.STYLE_OVERRIDES,
      JSON.stringify({
        modern: { color: { primary: '1 2% 3%' } },
        'future-retro': { color: { primary: '9 9% 9%' } },
      })
    )
    localStorage.setItem(
      THEME_STORAGE_KEYS.STYLE_BACKGROUND_CONFIG,
      JSON.stringify({ 'future-retro': { page: { type: 'image', source: 'old-background' } } })
    )

    const config = loadThemeConfig()
    expect(config.dashboardStyle).toBe('modern')
    expect(config.styleTokenOverrides).toEqual({ modern: { color: { primary: '1 2% 3%' } } })
    expect(config.styleBackgroundConfig).toEqual({})
  })
})

describe('saveThemeConfig', () => {
  it('归一化后写入各存储 key', () => {
    saveThemeConfig(
      buildConfig({
        selectedPreset: 'dark',
        styleCustomCSS: { modern: '.x {}' },
        dashboardStyle: 'modern',
      })
    )

    expect(localStorage.getItem(THEME_STORAGE_KEYS.PRESET)).toBe('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEYS.DASHBOARD_STYLE)).toBe('modern')
    expect(JSON.parse(localStorage.getItem(THEME_STORAGE_KEYS.STYLE_CUSTOM_CSS)!)).toEqual({
      modern: '.x {}',
    })
    expect(JSON.parse(localStorage.getItem(THEME_STORAGE_KEYS.STYLE_OVERRIDES)!)).toEqual({})
  })
})

describe('saveThemePartial', () => {
  it('只覆盖给定字段并保留其余已存配置', () => {
    saveThemeConfig(buildConfig({ selectedPreset: 'dark', styleCustomCSS: { modern: '.x {}' } }))

    saveThemePartial({ selectedPreset: 'ocean' })

    const config = loadThemeConfig()
    expect(config.selectedPreset).toBe('ocean')
    expect(config.styleCustomCSS).toEqual({ modern: '.x {}' })
  })
})

describe('exportThemeJSON', () => {
  it('导出的 JSON 可解析且等于当前配置', () => {
    saveThemeConfig(buildConfig({ selectedPreset: 'dark', dashboardStyle: 'modern' }))

    const json = exportThemeJSON()

    expect(JSON.parse(json)).toEqual(loadThemeConfig())
  })
})

describe('importThemeJSON', () => {
  it('非法 JSON 时返回失败与格式错误信息', () => {
    const result = importThemeJSON('{oops')

    expect(result.success).toBe(false)
    expect(result.errors).toHaveLength(1)
    expect(result.errors[0]).toContain('Invalid JSON format')
  })

  it('非对象 JSON 时返回失败', () => {
    expect(importThemeJSON('42')).toEqual({
      success: false,
      errors: ['Configuration must be a JSON object'],
    })
  })

  it('缺少必填字段时汇总所有错误', () => {
    const result = importThemeJSON('{}')

    expect(result.success).toBe(false)
    expect(result.errors).toEqual(['selectedPreset must be a string'])
  })

  it('可选字段类型错误时报告错误且不写入存储', () => {
    const result = importThemeJSON(
      JSON.stringify({
        selectedPreset: 'light',
        styleTokenOverrides: 'oops',
        dashboardStyle: 42,
      })
    )

    expect(result.success).toBe(false)
    expect(result.errors).toEqual([
      'styleTokenOverrides must be an object',
      'dashboardStyle must be a string',
    ])
    expect(localStorage.getItem(THEME_STORAGE_KEYS.PRESET)).toBeNull()
  })

  it('合法配置导入成功并落盘', () => {
    const result = importThemeJSON(
      JSON.stringify({
        selectedPreset: 'dark',
        dashboardStyle: 'modern',
        styleCustomCSS: { modern: '.a { color: red; }' },
      })
    )

    expect(result).toEqual({ success: true, errors: [] })
    expect(localStorage.getItem(THEME_STORAGE_KEYS.PRESET)).toBe('dark')
    expect(localStorage.getItem(THEME_STORAGE_KEYS.DASHBOARD_STYLE)).toBe('modern')
    expect(JSON.parse(localStorage.getItem(THEME_STORAGE_KEYS.STYLE_CUSTOM_CSS)!)).toEqual({
      modern: '.a { color: red; }',
    })
  })
})

describe('resetThemeToDefault', () => {
  it('移除所有主题相关存储 key', () => {
    saveThemeConfig(buildConfig())
    localStorage.setItem(THEME_STORAGE_KEYS.MODE, 'dark')

    resetThemeToDefault()

    Object.values(THEME_STORAGE_KEYS).forEach((key) => {
      expect(localStorage.getItem(key)).toBeNull()
    })
  })
})
