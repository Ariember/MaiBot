/**
 * useQuickShortcuts —— 首页快捷菜单领域 hook（页面逻辑下沉）。
 *
 * 收编 index.tsx 的快捷菜单状态机：
 * - quickShortcutIds（localStorage 持久化）、dialog 开关、搜索关键字
 * - 插件快捷入口（pluginShortcuts / isPluginShortcutsLoading + 加载 effect）
 * - quickShortcutOptions / map / selected / filtered 派生态，toggle / reset 操作
 *
 * 设计判断：
 * - 快捷菜单内置项依赖外部交互态（重启、审核器、未审核数量），故由调用方注入
 *   handleRestart / isRestarting / uncheckedCount / onOpenReviewer，hook 负责编排其余全部逻辑。
 * - 插件快捷入口的纯函数 helper（id 编解码、schema 解析等）随 hook 一并下沉。
 */
import { BookOpen, ClipboardCheck, FileText, HardDrive, MessageSquare, Puzzle, RotateCcw, Settings } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'


import { getBotConfigSchema } from '@/lib/config-api'
import { buildTabGroupsFromSchema } from '@/lib/config-tab-groups'
import {
  getInstalledPlugins,
  getPluginConfigSchema,
  type InstalledPlugin,
  type PluginConfigSchema,
} from '@/lib/plugin-api'

import type { QuickShortcutDefinition } from '../types'

const HOME_QUICKACTIONS_LOGS_LABELS: Record<string, string> = {
  "view": "查看日志",
  "replyer": "回复日志",
  "planner": "规划日志",
  "reasoning": "推理日志",
}

const HOME_QUICKACTIONS_DESCRIPTIONS_LOGS_LABELS: Record<string, string> = {
  "view": "查看 WebUI 日志",
  "replyer": "查看回复阶段的推理记录",
  "planner": "查看规划阶段的推理记录",
  "reasoning": "打开推理日志",
}


const QUICK_SHORTCUT_STORAGE_KEY = 'maibot-home-quick-shortcuts'
const DEFAULT_QUICK_SHORTCUT_IDS = [
  'route:logs',
  'route:settings-appearance',
  'route:model-list',
  'route:chat',
  'route:logs:replyer',
  'route:logs:reasoning',
]
const SIDEBAR_REDUNDANT_SHORTCUT_IDS = new Set([
  'route:plugin-market',
  'route:plugin-config',
  'route:model-providers',
  'route:bot-config',
  'route:emoji',
  'route:expression',
])

function loadQuickShortcutIds(): string[] {
  const fallback = [...DEFAULT_QUICK_SHORTCUT_IDS]
  if (typeof window === 'undefined') {
    return fallback
  }

  const stored = localStorage.getItem(QUICK_SHORTCUT_STORAGE_KEY)
  if (!stored) {
    return fallback
  }

  try {
    const parsed = JSON.parse(stored)
    if (Array.isArray(parsed)) {
      const ids = parsed.filter(
        (item): item is string => typeof item === 'string' && item.length > 0
      )
      const uniqueIds = Array.from(new Set(ids))
      const filteredIds = uniqueIds.filter((id) => !SIDEBAR_REDUNDANT_SHORTCUT_IDS.has(id))
      const normalizedIds = filteredIds.length > 0 ? filteredIds : fallback
      if (
        normalizedIds.length !== uniqueIds.length ||
        normalizedIds.some((id, index) => id !== uniqueIds[index])
      ) {
        saveQuickShortcutIds(normalizedIds)
      }
      return normalizedIds
    }
  } catch {
    return fallback
  }

  return fallback
}

function saveQuickShortcutIds(ids: string[]): void {
  localStorage.setItem(QUICK_SHORTCUT_STORAGE_KEY, JSON.stringify(Array.from(new Set(ids))))
}

function getPluginShortcutId(pluginId: string, tabId?: string): string {
  const encodedPluginId = encodeURIComponent(pluginId)
  if (!tabId) {
    return `plugin-config:${encodedPluginId}`
  }
  return `plugin-config:${encodedPluginId}:tab:${encodeURIComponent(tabId)}`
}

function parsePluginShortcutId(id: string): { pluginId: string; tabId?: string } | null {
  if (!id.startsWith('plugin-config:')) {
    return null
  }

  const [, encodedPluginId, marker, encodedTabId] = id.split(':')
  if (!encodedPluginId) {
    return null
  }

  return {
    pluginId: decodeURIComponent(encodedPluginId),
    tabId: marker === 'tab' && encodedTabId ? decodeURIComponent(encodedTabId) : undefined,
  }
}

function getPluginConfigHref(pluginId: string, tabId?: string): string {
  const params = new URLSearchParams({ plugin: pluginId })
  if (tabId) {
    params.set('tab', tabId)
  }
  return `/plugin-config?${params.toString()}`
}

function buildBasePluginShortcut(plugin: InstalledPlugin): QuickShortcutDefinition {
  const pluginName = plugin.manifest.name || plugin.id
  return {
    id: getPluginShortcutId(plugin.id),
    category: 'plugin',
    label: `${pluginName} 配置`,
    description: `打开 ${pluginName} 的插件配置页面`,
    icon: Puzzle,
    href: getPluginConfigHref(plugin.id),
  }
}

async function loadPluginTabShortcuts(
  plugin: InstalledPlugin,
  selectedTabIds?: Set<string>
): Promise<QuickShortcutDefinition[]> {
  // 单个插件 schema 拉取失败不应中断整体快捷入口加载，按空处理
  let schema: PluginConfigSchema
  try {
    schema = await getPluginConfigSchema(plugin.id)
  } catch {
    return []
  }

  const pluginName = plugin.manifest.name || plugin.id
  const schemaTabs = schema.layout.type === 'tabs' ? schema.layout.tabs : []
  const tabs = selectedTabIds ? schemaTabs.filter((tab) => selectedTabIds.has(tab.id)) : schemaTabs
  return tabs.map((tab) => ({
    id: getPluginShortcutId(plugin.id, tab.id),
    category: 'plugin' as const,
    label: `${pluginName} / ${tab.title || tab.id}`,
    description: `打开 ${pluginName} 的 ${tab.title || tab.id} 标签页`,
    icon: Puzzle,
    href: getPluginConfigHref(plugin.id, tab.id),
  }))
}

function getSelectedPluginTabIds(ids: string[]): Map<string, Set<string>> {
  const selectedTabs = new Map<string, Set<string>>()
  for (const id of ids) {
    const parsed = parsePluginShortcutId(id)
    if (!parsed?.tabId) {
      continue
    }

    const pluginTabs = selectedTabs.get(parsed.pluginId) ?? new Set<string>()
    pluginTabs.add(parsed.tabId)
    selectedTabs.set(parsed.pluginId, pluginTabs)
  }
  return selectedTabs
}

function getSelectedPluginIds(ids: string[]): Set<string> {
  const selectedPluginIds = new Set<string>()
  for (const id of ids) {
    const parsed = parsePluginShortcutId(id)
    if (parsed) {
      selectedPluginIds.add(parsed.pluginId)
    }
  }
  return selectedPluginIds
}

function getFallbackPluginShortcut(id: string): QuickShortcutDefinition | null {
  const parsed = parsePluginShortcutId(id)
  if (!parsed) {
    return null
  }

  return {
    id,
    category: 'plugin',
    label: parsed.tabId
      ? `插件配置：${parsed.pluginId} / ${parsed.tabId}`
      : `插件配置：${parsed.pluginId}`,
    description: parsed.tabId
      ? '打开指定插件配置标签页'
      : '打开指定插件配置页面',
    icon: Puzzle,
    href: getPluginConfigHref(parsed.pluginId, parsed.tabId),
  }
}

interface UseQuickShortcutsParams {
  isRestarting: boolean
  handleRestart: () => void | Promise<void>
  uncheckedCount: number
  onOpenReviewer: () => void
}

export function useQuickShortcuts({
  isRestarting,
  handleRestart,
  uncheckedCount,
  onOpenReviewer,
}: UseQuickShortcutsParams) {
  const [quickShortcutIds, setQuickShortcutIds] = useState<string[]>(loadQuickShortcutIds)
  const [quickShortcutDialogOpen, setQuickShortcutDialogOpen] = useState(false)
  const [quickShortcutSearch, setQuickShortcutSearch] = useState('')
  const [pluginShortcuts, setPluginShortcuts] = useState<QuickShortcutDefinition[]>([])
  const [isPluginShortcutsLoading, setIsPluginShortcutsLoading] = useState(false)
  const configSchemaQuery = useQuery({
    queryKey: ['bot-config', 'schema'],
    queryFn: getBotConfigSchema,
    staleTime: Infinity,
  })
  const configShortcuts = useMemo<QuickShortcutDefinition[]>(
    () =>
      configSchemaQuery.data
        ? buildTabGroupsFromSchema(configSchemaQuery.data).map((tab) => ({
            id: `route:bot-config:${tab.id}`,
            category: 'config' as const,
            label: tab.label,
            description: `打开主程序配置 / ${tab.label}`,
            icon: Settings,
            href: `/config/bot?${new URLSearchParams({ tab: tab.id }).toString()}`,
          }))
        : [],
    [configSchemaQuery.data]
  )

  useEffect(() => {
    let cancelled = false

    const loadPluginShortcuts = async () => {
      const selectedPluginIds = getSelectedPluginIds(quickShortcutIds)
      const selectedPluginTabIds = getSelectedPluginTabIds(quickShortcutIds)
      if (!quickShortcutDialogOpen && selectedPluginIds.size === 0) {
        setPluginShortcuts([])
        setIsPluginShortcutsLoading(false)
        return
      }

      setIsPluginShortcutsLoading(true)
      try {
        const installed = await getInstalledPlugins()
        if (cancelled) {
          return
        }

        const enabledPlugins = installed
          .filter((plugin) => plugin.disabled !== true && plugin.enabled !== false)
          .filter((plugin, index, all) => index === all.findIndex((item) => item.id === plugin.id))

        const visiblePlugins = quickShortcutDialogOpen
          ? enabledPlugins
          : enabledPlugins.filter((plugin) => selectedPluginIds.has(plugin.id))
        const baseShortcuts = visiblePlugins.map((plugin) => buildBasePluginShortcut(plugin))
        if (!cancelled) {
          setPluginShortcuts(baseShortcuts)
        }

        if (selectedPluginTabIds.size === 0) {
          return
        }

        const enabledPluginMap = new Map(enabledPlugins.map((plugin) => [plugin.id, plugin]))
        const tabShortcuts = (
          await Promise.all(
            Array.from(selectedPluginTabIds.entries()).map(async ([pluginId, selectedTabIds]) => {
              const plugin = enabledPluginMap.get(pluginId)
              if (!plugin) {
                return []
              }

              try {
                return await loadPluginTabShortcuts(plugin, selectedTabIds)
              } catch (error) {
                console.warn(`加载插件 ${plugin.id} 已选配置页签快捷入口失败:`, error)
                return []
              }
            })
          )
        ).flat()

        if (!cancelled) {
          setPluginShortcuts([...baseShortcuts, ...tabShortcuts])
        }
      } catch (error) {
        console.error('加载插件快捷入口失败:', error)
      } finally {
        if (!cancelled) {
          setIsPluginShortcutsLoading(false)
        }
      }
    }

    void loadPluginShortcuts()

    return () => {
      cancelled = true
    }
  }, [quickShortcutDialogOpen, quickShortcutIds])

  const quickShortcutOptions = useMemo<QuickShortcutDefinition[]>(
    () => [
      {
        id: 'action:restart',
        category: 'system',
        label: isRestarting ? '重启中...' : '重启麦麦',
        description: '重启麦麦主程序',
        icon: RotateCcw,
        action: handleRestart,
        disabled: isRestarting,
      },
      {
        id: 'action:expression-review',
        category: 'resource',
        label: '表达审核',
        description: '打开表达学习审核弹窗',
        icon: ClipboardCheck,
        action: onOpenReviewer,
        badge:
          uncheckedCount > 0 ? (uncheckedCount > 99 ? '99+' : String(uncheckedCount)) : undefined,
      },
      {
        id: 'route:logs',
        category: 'monitor',
        label: '查看日志',
        description: '查看 WebUI 日志',
        icon: FileText,
        href: '/logs',
      },
      {
        id: 'route:chat',
        category: 'system',
        label: '麦麦聊聊',
        description: '打开麦麦聊天',
        icon: MessageSquare,
        href: '/chat',
      },
      {
        id: 'external:docs',
        category: 'external',
        label: '前往文档',
        description: '打开麦麦使用文档',
        icon: BookOpen,
        href: 'https://docs.mai-mai.org',
        external: true,
      },
      ...(['replyer', 'planner', 'reasoning'] as const).map((stage) => ({
        id: `route:logs:${stage}`,
        category: 'monitor' as const,
        label: HOME_QUICKACTIONS_LOGS_LABELS[stage],
        description: HOME_QUICKACTIONS_DESCRIPTIONS_LOGS_LABELS[stage],
        icon: FileText,
        href: stage === 'reasoning' ? '/reasoning-process' : `/reasoning-process?stage=${stage}`,
      })),
      ...configShortcuts,
      {
        id: 'route:settings-appearance',
        category: 'system',
        label: '外观设置',
        description: '打开设置 / 外观',
        icon: Settings,
        href: '/settings?tab=appearance',
      },
      {
        id: 'route:settings-local-cache',
        category: 'system',
        label: '本地缓存',
        description: '打开设置 / 本地缓存',
        icon: HardDrive,
        href: '/settings?tab=local-cache',
      },
      {
        id: 'route:model-list',
        category: 'config',
        label: '模型列表',
        description: '打开模型管理 / 模型列表',
        icon: Settings,
        href: '/config/model?tab=models',
      },
      {
        id: 'route:model-tasks',
        category: 'config',
        label: '模型功能分配',
        description: '打开模型管理 / 为模型分配功能',
        icon: Settings,
        href: '/config/model?tab=tasks',
      },
      ...pluginShortcuts,
    ],
    [configShortcuts, handleRestart, isRestarting, onOpenReviewer, pluginShortcuts, uncheckedCount]
  )

  const quickShortcutMap = useMemo(
    () => new Map(quickShortcutOptions.map((shortcut) => [shortcut.id, shortcut])),
    [quickShortcutOptions]
  )

  const selectedQuickShortcuts = useMemo(
    () =>
      quickShortcutIds
        .map((id) => quickShortcutMap.get(id) ?? getFallbackPluginShortcut(id))
        .filter((shortcut): shortcut is QuickShortcutDefinition => Boolean(shortcut)),
    [quickShortcutIds, quickShortcutMap]
  )

  const filteredQuickShortcutOptions = useMemo(() => {
    const query = quickShortcutSearch.trim().toLowerCase()
    if (!query) {
      return quickShortcutOptions
    }

    return quickShortcutOptions.filter((shortcut) =>
      `${shortcut.label} ${shortcut.description}`.toLowerCase().includes(query)
    )
  }, [quickShortcutOptions, quickShortcutSearch])

  const updateQuickShortcutIds = useCallback((nextIds: string[]) => {
    const normalizedIds = Array.from(new Set(nextIds))
    setQuickShortcutIds(normalizedIds)
    saveQuickShortcutIds(normalizedIds)
  }, [])

  const toggleQuickShortcut = useCallback(
    (id: string, checked: boolean) => {
      updateQuickShortcutIds(
        checked
          ? [...quickShortcutIds, id]
          : quickShortcutIds.filter((shortcutId) => shortcutId !== id)
      )
    },
    [quickShortcutIds, updateQuickShortcutIds]
  )

  const resetQuickShortcuts = useCallback(() => {
    updateQuickShortcutIds([...DEFAULT_QUICK_SHORTCUT_IDS])
  }, [updateQuickShortcutIds])

  return {
    quickShortcutIds,
    quickShortcutDialogOpen,
    setQuickShortcutDialogOpen,
    quickShortcutSearch,
    setQuickShortcutSearch,
    isPluginShortcutsLoading,
    selectedQuickShortcuts,
    filteredQuickShortcutOptions,
    toggleQuickShortcut,
    resetQuickShortcuts,
  }
}
