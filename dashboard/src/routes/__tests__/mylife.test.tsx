import type { ReactNode } from 'react'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MYLIFE_PLUGIN_ID } from '@/lib/mylife'
import { getInstalledPlugins, type InstalledPlugin } from '@/lib/plugin-api'

import { MyLifePage } from '../mylife'

vi.mock('@/lib/plugin-api', () => ({ getInstalledPlugins: vi.fn() }))
vi.mock('@tanstack/react-router', () => ({ useNavigate: () => vi.fn() }))
vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }))
vi.mock('@/components/ui/scroll-area', () => ({
  ScrollArea: ({ children }: { children: ReactNode }) => children,
}))
vi.mock('../plugin-config', () => ({
  PluginConfigEditor: ({ plugin, initialTab }: { plugin: InstalledPlugin; initialTab?: string }) => (
    <div data-testid="editor" data-plugin={plugin.id} data-enabled={plugin.enabled} data-tab={initialTab} />
  ),
}))

afterEach(() => {
  cleanup()
  window.history.replaceState(null, '', '/')
})

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><MyLifePage /></QueryClientProvider>)
}

describe('麦日常配置', () => {
  it('禁用时仍加载内置配置编辑器并保留分组深链接', async () => {
    window.history.replaceState(null, '', '/mylife?tab=schedule')
    vi.mocked(getInstalledPlugins).mockResolvedValue([
      { id: 'another.plugin', enabled: true } as InstalledPlugin,
      { id: MYLIFE_PLUGIN_ID, builtin: true, enabled: false } as InstalledPlugin,
    ])
    renderPage()
    const editor = await screen.findByTestId('editor')
    expect(editor).toHaveAttribute('data-plugin', MYLIFE_PLUGIN_ID)
    expect(editor).toHaveAttribute('data-enabled', 'false')
    expect(editor).toHaveAttribute('data-tab', 'schedule')
    expect(getInstalledPlugins).toHaveBeenCalledWith({ includeBuiltin: true })
  })

  it('展示加载错误并允许重试', async () => {
    vi.mocked(getInstalledPlugins)
      .mockRejectedValueOnce(new Error('连接中断'))
      .mockResolvedValueOnce([])
    renderPage()
    expect(await screen.findByText('连接中断')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'pluginWebUI.refresh' }))
    expect(await screen.findByText('mylife.unavailable')).toBeInTheDocument()
    expect(screen.queryByTestId('editor')).not.toBeInTheDocument()
  })
})
