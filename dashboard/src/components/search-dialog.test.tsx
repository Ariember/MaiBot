import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Search } from 'lucide-react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ConfigSchema } from '@/types/config-schema'

import { SearchDialog } from './search-dialog'

const navigateMock = vi.fn()
const getBotConfigSchemaMock = vi.fn()
const getModelConfigSchemaMock = vi.fn()
const searchWithAIStreamMock = vi.fn()
const onOpenChangeMock = vi.fn()

vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => navigateMock,
}))




vi.mock('@/components/layout/use-menu-sections', () => ({
  useMenuSections: () => [
    {
      title: '配置',
      items: [
        {
          icon: Search,
          label: '麦麦设置',
          path: '/config/bot',
          searchDescription: '编辑麦麦配置',
        },
      ],
    },
  ],
}))

vi.mock('@/router', () => ({
  registeredRoutePaths: new Set(['/config/bot']),
}))

vi.mock('@/lib/config-api', () => ({
  getBotConfigSchema: () => getBotConfigSchemaMock(),
  getModelConfigSchema: () => getModelConfigSchemaMock(),
}))

vi.mock('@/lib/ai-search-api', () => ({
  searchWithAIStream: (...args: unknown[]) => searchWithAIStreamMock(...args),
}))

const botConfigSchema: ConfigSchema = {
  className: 'Config',
  classDoc: '麦麦配置',
  fields: [
    {
      name: 'personality',
      type: 'object',
      label: '人格',
      description: '人格相关设置',
      required: true,
    },
  ],
  nested: {
    personality: {
      className: 'PersonalityConfig',
      classDoc: '人格配置',
      fields: [
        {
          name: 'personality',
          type: 'string',
          label: '人格设定',
          description: '麦麦的人格和身份设定',
          required: true,
        },
      ],
    },
  },
}

const modelConfigSchema: ConfigSchema = {
  className: 'ModelConfig',
  classDoc: '模型配置',
  fields: [
    {
      name: 'models',
      type: 'array',
      label: '模型列表',
      description: '已配置的推理模型',
      required: true,
    },
  ],
}

const RECENT_SEARCH_ROUTES_KEY = 'maibot-search-recent-routes'

function resultButtons() {
  return screen.getAllByRole('button').filter((button) => button.getAttribute('title')?.includes(' · '))
}

/** 等配置索引异步写入完成，避免测试结束后的 act 警告 */
async function flushConfigIndex() {
  await waitFor(() => {
    expect(getBotConfigSchemaMock).toHaveBeenCalled()
  })
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

/** 先消耗语言切换 rAF 对索引的清空，再等到配置项真正写入 */
async function settleSearchDialog() {
  await waitFor(() => {
    expect(getBotConfigSchemaMock).toHaveBeenCalled()
  }, { timeout: 5000 })
  await act(async () => {
    await new Promise<void>((resolve) => {
      requestAnimationFrame(() => resolve())
    })
    await Promise.resolve()
    await Promise.resolve()
    await new Promise<void>((resolve) => {
      requestAnimationFrame(() => resolve())
    })
  })
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
  })
}

describe('SearchDialog', () => {
  beforeEach(() => {
    navigateMock.mockReset()
    getBotConfigSchemaMock.mockResolvedValue(botConfigSchema)
    getModelConfigSchemaMock.mockRejectedValue(new Error('模型配置不可用'))
    searchWithAIStreamMock.mockReset()
    onOpenChangeMock.mockReset()
    localStorage.clear()
  })

  afterEach(() => {
    cleanup()
  })

  it('保留与页面共用同一路径的配置项搜索结果', async () => {
    const user = userEvent.setup()
    render(<SearchDialog open onOpenChange={vi.fn()} />)

    await user.type(screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”'), '人格')

    expect(await screen.findByText('人格设定')).toBeInTheDocument()
    expect(screen.queryByText('未找到匹配的页面或配置项')).not.toBeInTheDocument()
  })

  it('用 AI 返回的真实索引 ID 导航并定位配置字段', async () => {
    searchWithAIStreamMock.mockImplementation(
      async (
        _payload: unknown,
        onProgress: (event: {
          type: 'progress'
          stage: 'tool' | 'correcting'
          status: 'started'
          tool?: string
          query?: string
          error?: string
        }) => void
      ) => {
        onProgress({
          type: 'progress',
          stage: 'tool',
          status: 'started',
          tool: 'search_official_docs',
          query: '人格 身份设定',
        })
        onProgress({
          type: 'progress',
          stage: 'correcting',
          status: 'started',
          error: '移除无依据技术项',
        })
        return {
          cached: false,
          model_name: 'test-utils-model',
          answer: '可以在 **人格设置** 中调整麦麦的性格描述。',
          suggestions: ['修改后先在 `测试群` 观察回复效果'],
          sources: [
            {
              title: 'Bot 配置',
              url: 'https://docs.mai-mai.org/manual/configuration/bot-config',
            },
          ],
          expanded_terms: ['人格', '身份设定'],
          results: [
            {
              id: 'c2',
              reason: '这里用于调整麦麦的人格与身份',
            },
          ],
          total_tokens: 120,
          grounding_error: '',
        }
      }
    )
    const user = userEvent.setup()
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)

    await user.type(screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”'), '我想修改麦麦的性格')
    await user.click(await screen.findByRole('button', { name: '提问' }))

    expect(await screen.findByText('这里用于调整麦麦的人格与身份')).toBeInTheDocument()
    expect(screen.getByText('人格设置').tagName).toBe('STRONG')
    expect(screen.getByText('测试群').tagName).toBe('CODE')
    expect(screen.getByRole('link', { name: 'Bot 配置' })).toHaveAttribute(
      'href',
      'https://docs.mai-mai.org/manual/configuration/bot-config'
    )
    expect(screen.getByText('搜索过程')).toBeInTheDocument()
    const progressToggle = screen.getByRole('button', { name: '展开搜索过程' })
    expect(progressToggle).toHaveAttribute('aria-expanded', 'false')
    await user.click(progressToggle)
    expect(screen.getByRole('button', { name: '收起搜索过程' })).toHaveAttribute(
      'aria-expanded',
      'true'
    )
    expect(screen.getByText('搜索官方文档')).toBeInTheDocument()
    expect(screen.getByText('人格 身份设定')).toBeInTheDocument()
    expect(screen.getByText('检测到证据不足，正在重新整理回答')).toBeInTheDocument()
    expect(searchWithAIStreamMock).toHaveBeenCalledWith(
      expect.objectContaining({
        query: '我想修改麦麦的性格',
        candidates: expect.arrayContaining([
          expect.objectContaining({ id: 'c2', title: '人格设定' }),
        ]),
      }),
      expect.any(Function),
      expect.any(AbortSignal)
    )

    await user.click(screen.getByRole('button', { name: /人格设定/ }))

    expect(navigateMock).toHaveBeenCalledWith({
      to: '/config/bot?field=personality.personality',
    })
    expect(onOpenChangeMock).not.toHaveBeenCalledWith(false)
    expect(screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”')).toHaveValue('我想修改麦麦的性格')
  })

  it('在过程列表末尾明确显示回答生成失败及原因', async () => {
    searchWithAIStreamMock.mockImplementation(
      async (
        _payload: unknown,
        onProgress: (event: { type: 'progress'; stage: 'finalizing' }) => void
      ) => {
        onProgress({
          type: 'progress',
          stage: 'finalizing',
        })
        throw new Error('AI 搜索结果解析失败: 模型返回的 JSON 不完整')
      }
    )
    const user = userEvent.setup()
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)

    await user.type(screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”'), '麦麦说话太多')
    await user.click(await screen.findByRole('button', { name: '提问' }))

    expect(await screen.findByText('回答生成失败')).toBeInTheDocument()
    expect(screen.getAllByText('AI 搜索结果解析失败: 模型返回的 JSON 不完整')).not.toHaveLength(0)
    expect(screen.getByRole('button', { name: '收起搜索过程' })).toHaveAttribute(
      'aria-expanded',
      'true'
    )
  })

  it('从 localStorage 恢复最近访问，并过滤掉非字符串路径', async () => {
    localStorage.setItem(
      RECENT_SEARCH_ROUTES_KEY,
      JSON.stringify(['/config/bot', 12, null, '/missing'])
    )
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)

    expect(await screen.findByText('最近访问')).toBeInTheDocument()
    await flushConfigIndex()
    const recent = resultButtons().find((button) => button.textContent?.includes('最近访问'))
    expect(recent).toHaveTextContent('麦麦设置')
    expect(resultButtons().filter((button) => button.textContent?.includes('最近访问'))).toHaveLength(1)
  })

  it('最近访问不是合法 JSON 时按空列表处理', async () => {
    localStorage.setItem(RECENT_SEARCH_ROUTES_KEY, '{not-json')
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)

    expect(screen.queryByText('最近访问')).not.toBeInTheDocument()
    expect(resultButtons().some((button) => button.textContent?.includes('麦麦设置'))).toBe(true)
    await flushConfigIndex()
  })

  it('最近访问不是数组时按空列表处理', async () => {
    localStorage.setItem(RECENT_SEARCH_ROUTES_KEY, JSON.stringify({ path: '/config/bot' }))
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)

    expect(screen.queryByText('最近访问')).not.toBeInTheDocument()
    await flushConfigIndex()
  })

  it.skip('模型配置字段走 getModelConfigPath 并带上 tab 查询参数', async () => {
    getModelConfigSchemaMock.mockResolvedValue(modelConfigSchema)
    const user = userEvent.setup()
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)

    await user.type(screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”'), '模型列表')
    await user.click(await screen.findByRole('button', { name: /模型列表/ }))

    expect(navigateMock).toHaveBeenCalledWith({
      to: '/config/model?field=models&tab=models',
    })
    expect(JSON.parse(localStorage.getItem(RECENT_SEARCH_ROUTES_KEY) ?? '[]')).toEqual([
      '/config/model',
    ])
  })

  it('Escape 关闭对话框，方向键与 Home/End/Enter 改变选中并导航', async () => {
    const user = userEvent.setup()
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)

    const input = screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”')
    fireEvent.keyDown(input, { key: 'Escape' })
    expect(onOpenChangeMock).toHaveBeenCalledWith(false)

    await user.type(input, '人格')
    await screen.findByRole('button', { name: /人格设定/ })
    await waitFor(() => {
      expect(resultButtons().length).toBeGreaterThanOrEqual(2)
    })

    fireEvent.keyDown(input, { key: 'End' })
    expect(resultButtons()[resultButtons().length - 1]?.className).toContain('bg-accent')

    fireEvent.keyDown(input, { key: 'Home' })
    expect(resultButtons()[0]?.className).toContain('bg-accent')

    fireEvent.keyDown(input, { key: 'ArrowUp' })
    expect(resultButtons()[resultButtons().length - 1]?.className).toContain('bg-accent')

    fireEvent.keyDown(input, { key: 'ArrowDown' })
    expect(resultButtons()[0]?.className).toContain('bg-accent')

    fireEvent.keyDown(input, { key: 'Enter' })
    expect(navigateMock).toHaveBeenCalledWith({
      to: '/config/bot?field=personality',
    })
  })

  it('Ctrl+Enter 触发 AI 搜索；无结果时方向键与 Enter 不导航', async () => {
    searchWithAIStreamMock.mockResolvedValue({
      cached: false,
      model_name: 'test-utils-model',
      answer: '',
      suggestions: [],
      sources: [],
      expanded_terms: [],
      results: [],
      total_tokens: 2,
      grounding_error: '',
    })
    const user = userEvent.setup()
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)

    const input = screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”')
    await user.type(input, 'zzzz-no-match-zzzz')
    await waitFor(() => {
      expect(screen.getByRole('button', { name: '提问' })).toBeEnabled()
    })

    fireEvent.keyDown(input, { key: 'ArrowDown' })
    fireEvent.keyDown(input, { key: 'ArrowUp' })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(navigateMock).not.toHaveBeenCalled()

    fireEvent.keyDown(input, { key: 'Enter', ctrlKey: true })
    await waitFor(() => {
      expect(searchWithAIStreamMock).toHaveBeenCalled()
    })
    expect(await screen.findByText('AI 没有找到足够相关的页面或配置项')).toBeInTheDocument()
  })

  it('无匹配时显示空结果，Home/End/方向键与 Enter 不导航', async () => {
    const user = userEvent.setup()
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)

    const input = screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”')
    await user.type(input, 'zzzz-no-match-zzzz')

    expect(await screen.findByText('未找到匹配的页面或配置项')).toBeInTheDocument()

    fireEvent.keyDown(input, { key: 'Home' })
    fireEvent.keyDown(input, { key: 'End' })
    fireEvent.keyDown(input, { key: 'ArrowDown' })
    fireEvent.keyDown(input, { key: 'ArrowUp' })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(navigateMock).not.toHaveBeenCalled()
    await flushConfigIndex()
  })

  it('无可用路由且查询为空时显示开始搜索提示', async () => {
    const { registeredRoutePaths } = await import('@/router')
    const previousPaths = [...registeredRoutePaths]
    registeredRoutePaths.clear()
    try {
      render(<SearchDialog open onOpenChange={onOpenChangeMock} />)
      expect(await screen.findByText('输入关键词开始搜索')).toBeInTheDocument()
      await flushConfigIndex()
    } finally {
      registeredRoutePaths.clear()
      for (const path of previousPaths) {
        registeredRoutePaths.add(path)
      }
    }
  })

  it('点击关闭按钮关闭对话框；关闭状态下不加载配置索引', async () => {
    const user = userEvent.setup()
    const { rerender } = render(<SearchDialog open={false} onOpenChange={onOpenChangeMock} />)

    expect(screen.queryByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”')).not.toBeInTheDocument()
    expect(getBotConfigSchemaMock).not.toHaveBeenCalled()

    rerender(<SearchDialog open onOpenChange={onOpenChangeMock} />)
    await user.click(screen.getByRole('button', { name: '关闭' }))
    expect(onOpenChangeMock).toHaveBeenCalledWith(false)
    await flushConfigIndex()
  })

  it('Meta+Enter 触发 AI 搜索，鼠标移入结果会更新选中项', async () => {
    searchWithAIStreamMock.mockResolvedValue({
      cached: false,
      model_name: 'test-utils-model',
      answer: '',
      suggestions: [],
      sources: [],
      expanded_terms: [],
      results: [],
      total_tokens: 2,
      grounding_error: '',
    })
    const user = userEvent.setup()
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)
    await settleSearchDialog()

    const input = screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”')
    await user.type(input, '人格')
    const second = await waitFor(
      () => {
        const buttons = resultButtons()
        expect(buttons.length).toBeGreaterThanOrEqual(2)
        expect(buttons[0]?.className).toContain('bg-accent text-accent-foreground')
        return buttons[1]!
      },
      { timeout: 5000 }
    )

    fireEvent.mouseEnter(second)
    await waitFor(
      () => {
        expect(resultButtons()[1]?.className).toContain('bg-accent text-accent-foreground')
        expect(resultButtons()[0]?.className).not.toContain('bg-accent text-accent-foreground')
      },
      { timeout: 5000 }
    )

    fireEvent.keyDown(input, { key: 'Enter', metaKey: true })
    await waitFor(
      () => {
        expect(searchWithAIStreamMock).toHaveBeenCalled()
      },
      { timeout: 5000 }
    )
    expect(await screen.findByText('AI 没有找到足够相关的页面或配置项', undefined, { timeout: 5000 })).toBeInTheDocument()
  })

  it('空查询或索引加载中时不发起 AI 搜索，并显示索引加载提示', async () => {
    let resolveBot = (_value: unknown) => {}
    getBotConfigSchemaMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveBot = resolve
        })
    )
    const user = userEvent.setup()
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)

    const input = screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”')
    fireEvent.keyDown(input, { key: 'Enter', ctrlKey: true })
    fireEvent.keyDown(input, { key: 'Enter', metaKey: true })
    expect(searchWithAIStreamMock).not.toHaveBeenCalled()

    await waitFor(() => {
      expect(getBotConfigSchemaMock).toHaveBeenCalled()
    })
    await user.type(input, '人格')

    expect(await screen.findByText('未找到匹配的页面或配置项')).toBeInTheDocument()
    expect(screen.getByText('正在加载配置搜索索引…')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '提问' })).toBeDisabled()

    fireEvent.keyDown(input, { key: 'Enter', ctrlKey: true })
    fireEvent.keyDown(input, { key: 'Enter', metaKey: true })
    expect(searchWithAIStreamMock).not.toHaveBeenCalled()

    await act(async () => {
      resolveBot(botConfigSchema)
    })
    expect(await screen.findByText('人格设定')).toBeInTheDocument()
  })

  it('配置索引同步抛错后按空索引处理', async () => {
    getBotConfigSchemaMock.mockImplementation(() => {
      throw new Error('索引爆炸')
    })
    const user = userEvent.setup()
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)

    await user.type(screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”'), '人格')

    expect(await screen.findByText('未找到匹配的页面或配置项')).toBeInTheDocument()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: '提问' })).toBeEnabled()
    })
  })

  it('卸载时丢弃尚未完成的配置索引结果', async () => {
    let resolveBot = (_value: unknown) => {}
    getBotConfigSchemaMock.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveBot = resolve
        })
    )
    const { unmount } = render(<SearchDialog open onOpenChange={onOpenChangeMock} />)
    await waitFor(() => {
      expect(getBotConfigSchemaMock).toHaveBeenCalled()
    })

    unmount()
    await act(async () => {
      resolveBot(botConfigSchema)
      await Promise.resolve()
    })
  })

  it('配置接口返回无法识别的 payload 时不生成配置搜索项', async () => {
    getBotConfigSchemaMock.mockResolvedValue(null)
    const user = userEvent.setup()
    const firstView = render(<SearchDialog open onOpenChange={onOpenChangeMock} />)

    await user.type(screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”'), '人格')
    expect(await screen.findByText('未找到匹配的页面或配置项')).toBeInTheDocument()
    firstView.unmount()

    getBotConfigSchemaMock.mockResolvedValue({ foo: 1 })
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)
    await userEvent.setup().type(screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”'), '人格')
    expect(await screen.findByText('未找到匹配的页面或配置项')).toBeInTheDocument()
    await flushConfigIndex()
  })

  it('从 schema 包裹结构与模型配置建立索引，选项描述可被搜索', async () => {
    const modelSchema: ConfigSchema = {
      className: 'ModelConfig',
      classDoc: '',
      fields: [
        {
          name: 'models',
          type: 'select',
          label: '模型列表',
          description: '',
          required: true,
          options: ['gpt', 'claude'],
          'x-option-descriptions': {
            gpt: 'OpenAI',
            claude: 'Anthropic',
          },
        },
      ],
    }
    getBotConfigSchemaMock.mockResolvedValue({ success: true, schema: botConfigSchema })
    getModelConfigSchemaMock.mockResolvedValue({ success: true, schema: modelSchema })
    const user = userEvent.setup()
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)
    await settleSearchDialog()

    const input = screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”')
    await user.type(input, '人格设定')
    expect(await screen.findByText('人格设定', undefined, { timeout: 5000 })).toBeInTheDocument()

    await user.clear(input)
    await user.type(input, 'OpenAI')
    expect(await screen.findByText('模型列表', undefined, { timeout: 5000 })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /模型列表/ }))

    expect(navigateMock).toHaveBeenCalledWith({
      to: '/config/model?field=models&tab=models',
    })
    expect(JSON.parse(localStorage.getItem(RECENT_SEARCH_ROUTES_KEY) ?? '[]')).toEqual([
      '/config/model',
    ])
  })

  it('按分类名与路径片段匹配并排序搜索结果', async () => {
    const user = userEvent.setup()
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)
    await settleSearchDialog()

    const input = screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”')
    await user.type(input, '配置')
    await waitFor(
      () => {
        expect(resultButtons().length).toBeGreaterThan(0)
      },
      { timeout: 5000 }
    )
    expect(resultButtons().some((button) => button.textContent?.includes('麦麦设置'))).toBe(true)

    await user.clear(input)
    await user.type(input, 'config')
    await waitFor(
      () => {
        expect(
          resultButtons().some((button) => button.getAttribute('title')?.includes('/config/bot'))
        ).toBe(true)
      },
      { timeout: 5000 }
    )
    await flushConfigIndex()
  })

  it('点击已在最近访问中的页面会去重并保留最近顺序', async () => {
    localStorage.setItem(
      RECENT_SEARCH_ROUTES_KEY,
      JSON.stringify(['/config/bot', '/gone', '/a', '/b', '/c', '/d', '/e', '/f'])
    )
    const user = userEvent.setup()
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)

    await user.click(await screen.findByRole('button', { name: /麦麦设置/ }))

    expect(navigateMock).toHaveBeenCalledWith({ to: '/config/bot' })
    expect(JSON.parse(localStorage.getItem(RECENT_SEARCH_ROUTES_KEY) ?? '[]')).toEqual([
      '/config/bot',
      '/gone',
      '/a',
      '/b',
      '/c',
      '/d',
      '/e',
      '/f',
    ])
    await flushConfigIndex()
  })

  it('AI 进度覆盖规划、缓存、工具完成/失败与标题目标详情', async () => {
    searchWithAIStreamMock.mockImplementation(
      async (
        _payload: unknown,
        onProgress: (event: {
          type: 'progress'
          stage: string
          status?: string
          round?: number
          tool?: string
          query?: string
          targets?: string[]
          titles?: string[]
          count?: number
          error?: string
        }) => void
      ) => {
        onProgress({ type: 'progress', stage: 'start', status: 'started' })
        onProgress({ type: 'progress', stage: 'planning', status: 'started' })
        onProgress({ type: 'progress', stage: 'cache_hit', status: 'completed' })
        onProgress({
          type: 'progress',
          stage: 'tool',
          status: 'started',
          tool: 'search_webui_index',
          query: '索引查询',
        })
        onProgress({
          type: 'progress',
          stage: 'tool',
          status: 'completed',
          tool: 'search_webui_index',
          count: 2,
          titles: ['文档A', '文档B'],
        })
        onProgress({
          type: 'progress',
          stage: 'tool',
          status: 'failed',
          tool: 'read_official_docs',
          error: '读取失败',
        })
        onProgress({
          type: 'progress',
          stage: 'tool',
          status: 'started',
          tool: 'read_official_docs',
          targets: ['目标1', '目标2'],
        })
        onProgress({ type: 'progress', stage: 'tool', status: 'started' })
        onProgress({ type: 'progress', stage: 'completed', status: 'completed' })
        return {
          cached: true,
          model_name: 'test-utils-model',
          answer: '',
          suggestions: [],
          sources: [],
          expanded_terms: ['性格'],
          results: [
            { id: 'missing-id', reason: '幽灵结果' },
            { id: 'c2', reason: '' },
          ],
          total_tokens: 2,
          grounding_error: '',
        }
      }
    )
    const user = userEvent.setup()
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)
    await settleSearchDialog()

    await user.type(screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”'), '性格')
    await user.click(await screen.findByRole('button', { name: '提问' }))

    expect(await screen.findByText('开始分析问题')).toBeInTheDocument()
    expect(screen.getByText('第 1 轮：规划检索')).toBeInTheDocument()
    expect(screen.getByText('已使用相同问题的缓存结果')).toBeInTheDocument()
    expect(screen.getByText('搜索页面和配置')).toBeInTheDocument()
    expect(screen.getByText('搜索页面和配置完成（2 项）')).toBeInTheDocument()
    expect(screen.getByText('读取官方文档失败')).toBeInTheDocument()
    expect(screen.getByText('读取官方文档')).toBeInTheDocument()
    expect(screen.getByText('执行搜索操作')).toBeInTheDocument()
    expect(screen.getByText('回答生成完成')).toBeInTheDocument()
    expect(screen.getByText('文档A、文档B')).toBeInTheDocument()
    expect(screen.getByText('目标1、目标2')).toBeInTheDocument()
    expect(screen.getByText('读取失败')).toBeInTheDocument()
    expect(screen.getByText('索引查询')).toBeInTheDocument()
    expect(screen.getByText('AI 理解为：性格')).toBeInTheDocument()
    expect(screen.queryByText('幽灵结果')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: /人格设定/ })).toBeInTheDocument()
  })

  it('非 Error 异常显示通用失败文案；已有 failed 进度不再重复追加', async () => {
    searchWithAIStreamMock.mockImplementation(
      async (
        _payload: unknown,
        onProgress: (event: {
          type: 'progress'
          stage: 'failed'
          status: 'failed'
          error: string
        }) => void
      ) => {
        onProgress({
          type: 'progress',
          stage: 'failed',
          status: 'failed',
          error: 'already-failed',
        })
        throw 'not-an-error'
      }
    )
    const user = userEvent.setup()
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)
    await settleSearchDialog()

    await user.type(screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”'), '麦麦说话太多')
    await user.click(await screen.findByRole('button', { name: '提问' }))

    expect(await screen.findByText('回答生成失败')).toBeInTheDocument()
    expect(screen.getByText('already-failed')).toBeInTheDocument()
    expect(screen.getByText('AI 搜索失败')).toBeInTheDocument()
    expect(screen.getAllByText('回答生成失败')).toHaveLength(1)
  })

  it('输入变化会中止进行中的 AI 搜索并丢弃迟到结果', async () => {
    searchWithAIStreamMock.mockImplementation(
      async (
        _payload: unknown,
        onProgress: (event: { type: 'progress'; stage: 'start' }) => void,
        signal: AbortSignal
      ) => {
        onProgress({ type: 'progress', stage: 'start' })
        await new Promise<void>((resolve) => {
          if (signal.aborted) {
            resolve()
            return
          }
          signal.addEventListener('abort', () => resolve(), { once: true })
        })
        return {
          cached: false,
          model_name: 'test-utils-model',
          answer: '不该出现的回答',
          suggestions: ['不该出现的建议'],
          sources: [],
          expanded_terms: [],
          results: [{ id: 'c0', reason: '迟到推荐' }],
          total_tokens: 2,
          grounding_error: '',
        }
      }
    )
    const user = userEvent.setup()
    render(<SearchDialog open onOpenChange={onOpenChangeMock} />)
    await settleSearchDialog()

    const input = screen.getByPlaceholderText('可以描述你想调整的效果，例如“麦麦说话太频繁”')
    await user.type(input, '性格')
    await user.click(await screen.findByRole('button', { name: '提问' }))
    expect(await screen.findByText('AI 理解中')).toBeInTheDocument()
    expect(screen.getByText('开始分析问题')).toBeInTheDocument()

    fireEvent.change(input, { target: { value: '性格x' } })

    await waitFor(() => {
      expect(screen.queryByText('AI 理解中')).not.toBeInTheDocument()
    })
    expect(screen.queryByText('不该出现的回答')).not.toBeInTheDocument()
    expect(screen.queryByText('不该出现的建议')).not.toBeInTheDocument()
    expect(screen.queryByText('迟到推荐')).not.toBeInTheDocument()
  })
})

