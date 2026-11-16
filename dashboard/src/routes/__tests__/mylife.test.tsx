import type { ReactNode } from 'react'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { MYLIFE_PLUGIN_ID } from '@/lib/mylife'
import {
  getPluginConfigBundle,
  resetPluginConfig,
  updatePluginConfig,
  updatePluginConfigRaw,
  type ConfigFieldSchema,
  type PluginConfigBundle,
} from '@/lib/plugin-api'

import { MyLifePage } from '../mylife'

const { toastMock, navigateMock, blocker } = vi.hoisted(() => ({
  toastMock: vi.fn(),
  navigateMock: vi.fn(),
  blocker: {
    status: 'unblocked' as 'unblocked' | 'blocked',
    proceed: vi.fn(),
    reset: vi.fn(),
    options: undefined as { shouldBlockFn: () => boolean; enableBeforeUnload: boolean } | undefined,
  },
}))

vi.mock('@/lib/plugin-api', () => ({
  getPluginConfigBundle: vi.fn(),
  updatePluginConfig: vi.fn(),
  updatePluginConfigRaw: vi.fn(),
  resetPluginConfig: vi.fn(),
}))
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: toastMock }) }))
vi.mock('@/lib/plugin-webui', () => ({ refreshPluginWebUI: vi.fn() }))
vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => navigateMock,
  useRouterState: ({ select }: { select: (state: unknown) => unknown }) =>
    select({ location: { searchStr: window.location.search, pathname: window.location.pathname } }),
  useBlocker: (options: typeof blocker.options) => {
    blocker.options = options
    return blocker
  },
}))

vi.mock('@/components/ui/scroll-area', () => ({
  ScrollArea: ({ children }: { children: ReactNode }) => children,
}))
vi.mock('@/components/CodeEditor', () => ({
  CodeEditor: ({ value, onChange }: { value: string; onChange: (value: string) => void }) => (
    <textarea aria-label="TOML 配置" value={value} onChange={(event) => onChange(event.target.value)} />
  ),
}))

function field(name: string, label: string): ConfigFieldSchema {
  return {
    name,
    label,
    type: 'string',
    ui_type: 'input',
    default: '',
    description: '',
    required: false,
    hidden: false,
    disabled: false,
    order: 0,
  }
}

function makeBundle(overrides: Partial<PluginConfigBundle> = {}): PluginConfigBundle {
  const sections: [string, string, ConfigFieldSchema][] = [
    ['environment', '环境与天气', field('city', '城市')],
    ['users', '私聊用户', field('owner_only_terms', '专属称呼')],
    ['proactive', '主动私聊', field('work_start', '主动开始时间')],
    ['memory', '生活记忆', field('reminder_time', '提醒时间')],
    ['network', '联网', field('news_query', '新闻主题')],
    ['models', '模型', field('fast_task', '快速任务')],
    ['usage', '用量', field('label', '统计名称')],
  ]
  return {
    schema: {
      plugin_id: MYLIFE_PLUGIN_ID,
      plugin_info: { name: '麦日常', version: '1.3.0', description: '', author: '' },
      sections: Object.fromEntries(sections.map(([name, title, schemaField]) => [
        name,
        { name, title, collapsed: false, order: 0, fields: { [schemaField.name]: schemaField } },
      ])),
      layout: { type: 'auto', tabs: [] },
    },
    config: {
      plugin: { enabled: false, config_version: '1.21.0', admin_user_ids: ['123456'] },
      environment: { city: '上海', timezone: 'Asia/Shanghai' },
      users: { profiles: [{ user_id: '123456', enabled: true }], owner_only_terms: '主人' },
      proactive: { work_start: '09:00' },
      models: { fast_task: 'utils' },
      usage: { label: '日常' },
      custom_section: { retained: true },
    },
    rawConfig: '[plugin]\nenabled = false\n',
    ...overrides,
  }
}

beforeEach(() => {
  blocker.status = 'unblocked'
  blocker.options = undefined
  vi.mocked(getPluginConfigBundle).mockResolvedValue(makeBundle())
  vi.mocked(updatePluginConfig).mockResolvedValue({ success: true, message: '已应用' })
  vi.mocked(updatePluginConfigRaw).mockResolvedValue({ success: true, message: '已应用' })
})

afterEach(() => {
  cleanup()
  window.history.replaceState(null, '', '/')
})

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const page = () => <QueryClientProvider client={client}><MyLifePage /></QueryClientProvider>
  const view = render(page())
  return { ...view, rerenderPage: () => view.rerender(page()) }
}

async function findCityInput() {
  const input = screen.queryByLabelText('城市')
  if (input) return input
  fireEvent.click(await screen.findByRole('button', { name: /高级设置/ }))
  return screen.findByLabelText('城市')
}

describe('麦日常配置', () => {
  it('禁用时可编辑，启停与其他草稿一起保存并保留未展示的配置', async () => {
    const user = userEvent.setup()
    renderPage()
    fireEvent.change(await findCityInput(), { target: { value: '杭州' } })
    await user.click(screen.getByRole('switch', { name: '启用麦日常' }))
    await user.click(screen.getByRole('button', { name: '选择设置页面' }))
    await user.click(screen.getByRole('menuitem', { name: '私聊陪伴' }))
    expect(screen.getByLabelText('主动开始时间')).toHaveValue('09:00')
    expect(window.location.search).toBe('?tab=private')
    await user.click(screen.getByRole('button', { name: '选择设置页面' }))
    await user.click(screen.getByRole('menuitem', { name: '基础设置' }))
    expect(await findCityInput()).toHaveValue('杭州')
    expect(updatePluginConfig).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: '保存并应用' }))
    await waitFor(() => expect(updatePluginConfig).toHaveBeenCalledWith(MYLIFE_PLUGIN_ID, {
      ...makeBundle().config,
      plugin: { enabled: true, config_version: '1.21.0', admin_user_ids: ['123456'] },
      environment: { city: '杭州', timezone: 'Asia/Shanghai' },
    }))
    expect(getPluginConfigBundle).toHaveBeenCalledWith(MYLIFE_PLUGIN_ID)
  })

  it('保存失败保留修改，允许再次保存', async () => {
    vi.mocked(updatePluginConfig)
      .mockRejectedValueOnce(new Error('连接中断'))
      .mockResolvedValueOnce({ success: true, message: '已应用' })
    renderPage()
    fireEvent.change(await findCityInput(), { target: { value: '杭州' } })
    fireEvent.click(screen.getByRole('button', { name: '保存并应用' }))
    expect(await screen.findByText('连接中断')).toBeInTheDocument()
    expect(await findCityInput()).toHaveValue('杭州')
    fireEvent.click(screen.getByRole('button', { name: '保存并应用' }))
    await waitFor(() => expect(updatePluginConfig).toHaveBeenCalledTimes(2))
  })

  it('撤销恢复全部草稿，不向服务端写入', async () => {
    const user = userEvent.setup()
    renderPage()
    fireEvent.change(await findCityInput(), { target: { value: '杭州' } })
    await user.click(screen.getByRole('switch', { name: '启用麦日常' }))
    await user.click(screen.getByRole('button', { name: '撤销更改' }))
    expect(await findCityInput()).toHaveValue('上海')
    expect(screen.getByRole('switch', { name: '启用麦日常' })).not.toBeChecked()
    expect(updatePluginConfig).not.toHaveBeenCalled()
  })

  it.each([
    ['environment', '基础设置', '城市'],
    ['users', '私聊陪伴', '专属称呼'],
    ['proactive', '私聊陪伴', '主动开始时间'],
    ['usage', '模型与用量', '统计名称'],
  ])('旧配置节 %s 的链接打开对应分组', async (section, group, label) => {
    window.history.replaceState(null, '', `/mylife?tab=${section}`)
    renderPage()
    expect(await screen.findByRole('button', { name: '选择设置页面' })).toHaveTextContent(group)
    if (section === 'users' || section === 'usage' || section === 'environment') {
      fireEvent.click(screen.getByRole('button', { name: /高级设置/ }))
    }
    expect(await screen.findByLabelText(label)).toBeVisible()
  })

  it('加载错误可重试并恢复可编辑页面', async () => {
    vi.mocked(getPluginConfigBundle).mockRejectedValueOnce(new Error('连接中断'))
    renderPage()
    expect(await screen.findByText('连接中断')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '重新加载' }))
    expect(await findCityInput()).toHaveValue('上海')
  })

  it('返回已有缓存的页面时显示服务端最新配置', async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    client.setQueryData(['mylife', 'config'], makeBundle())
    vi.mocked(getPluginConfigBundle).mockResolvedValue(makeBundle({
      config: { ...makeBundle().config, environment: { city: '杭州', timezone: 'Asia/Shanghai' } },
    }))
    render(<QueryClientProvider client={client}><MyLifePage /></QueryClientProvider>)
    expect(await findCityInput()).toHaveValue('杭州')
    expect(screen.getByRole('button', { name: '保存并应用' })).toBeDisabled()
  })

  it('配置错误提供 TOML 修复入口，保存后重新加载可视化配置', async () => {
    vi.mocked(getPluginConfigBundle).mockResolvedValueOnce(makeBundle({
      schema: null,
      configError: '私聊用户 QQ 号不能重复',
      rawConfig: '[plugin]\nenabled = "invalid"\n',
    }))
    renderPage()
    const editor = await screen.findByLabelText('TOML 配置')
    expect(screen.getByText('私聊用户 QQ 号不能重复')).toBeInTheDocument()
    fireEvent.change(editor, { target: { value: '[plugin]\nenabled = false\n' } })
    fireEvent.click(screen.getByRole('button', { name: '保存并应用' }))
    await waitFor(() => expect(updatePluginConfigRaw).toHaveBeenCalledWith(MYLIFE_PLUGIN_ID, '[plugin]\nenabled = false\n'))
    expect(await findCityInput()).toHaveValue('上海')
    expect(updatePluginConfig).not.toHaveBeenCalled()
  })

  it('未保存离开时保存失败仍停留，重试成功后才离开', async () => {
    vi.mocked(updatePluginConfig)
      .mockRejectedValueOnce(new Error('连接中断'))
      .mockResolvedValueOnce({ success: true, message: '已应用' })
    const { rerenderPage } = renderPage()
    fireEvent.change(await findCityInput(), { target: { value: '杭州' } })
    expect(blocker.options?.enableBeforeUnload).toBe(true)
    blocker.status = 'blocked'
    rerenderPage()
    fireEvent.click(await screen.findByRole('button', { name: '保存并离开' }))
    expect(await screen.findByText('连接中断')).toBeInTheDocument()
    expect(blocker.proceed).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '保存并离开' }))
    await waitFor(() => expect(blocker.proceed).toHaveBeenCalledTimes(1))
  })

  it('恢复默认设置须确认，成功后加载服务端默认值', async () => {
    vi.mocked(resetPluginConfig).mockResolvedValue({ success: true, message: '已重置' })
    renderPage()
    fireEvent.change(await findCityInput(), { target: { value: '杭州' } })
    fireEvent.click(screen.getByRole('button', { name: '恢复默认设置' }))
    let dialog = await screen.findByRole('dialog')
    expect(resetPluginConfig).not.toHaveBeenCalled()
    fireEvent.click(within(dialog).getByRole('button', { name: '继续编辑' }))
    expect(await findCityInput()).toHaveValue('杭州')
    fireEvent.click(screen.getByRole('button', { name: '恢复默认设置' }))
    dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: '恢复默认设置' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(resetPluginConfig).toHaveBeenCalledWith(MYLIFE_PLUGIN_ID)
    expect(await findCityInput()).toHaveValue('上海')
    expect(screen.getByRole('button', { name: '保存并应用' })).toBeDisabled()
  })

  it('恢复默认失败时保留当前草稿并显示错误', async () => {
    vi.mocked(resetPluginConfig).mockRejectedValue(new Error('无法备份配置'))
    renderPage()
    fireEvent.change(await findCityInput(), { target: { value: '杭州' } })
    fireEvent.click(screen.getByRole('button', { name: '恢复默认设置' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: '恢复默认设置' }))
    expect(await screen.findByText('无法备份配置')).toBeInTheDocument()
    expect(await findCityInput()).toHaveValue('杭州')
    expect(screen.getByRole('button', { name: '保存并应用' })).toBeEnabled()
  })
})
