import type { ReactElement, ReactNode } from 'react'

import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { backendApi } from '@/lib/http'

import { StatisticsPage } from '../index'
import type {
  DetailedStatisticsBreakdown,
  DetailedStatisticsData,
  DetailedStatisticsDistributions,
  DetailedStatisticsMetricsData,
  DetailedStatisticsPeriod,
  DetailedStatisticsSummary,
  DetailedStatisticsTrendData,
} from '../types'




vi.mock('recharts', async () => {
  const { cloneElement, isValidElement } = await import('react')
  const Stub = ({ children }: { children?: ReactNode }) => <div>{children}</div>
  return {
    __esModule: true,
    ResponsiveContainer: Stub,
    LineChart: Stub,
    Line: Stub,
    PieChart: Stub,
    Pie: Stub,
    Cell: Stub,
    XAxis: Stub,
    CartesianGrid: Stub,
    Legend: Stub,
    YAxis: ({
      tickFormatter,
      children,
    }: {
      tickFormatter?: (value: number) => string
      children?: ReactNode
    }) => (
      <div data-testid="chart-yaxis">
        {tickFormatter ? <span>{tickFormatter(12_000)}</span> : null}
        {tickFormatter ? <span>{tickFormatter(0.5)}</span> : null}
        {children}
      </div>
    ),
    Tooltip: ({ content, children }: { content?: ReactNode; children?: ReactNode }) => (
      <div data-testid="chart-tooltip">
        {isValidElement(content)
          ? cloneElement(content as ReactElement<Record<string, unknown>>, {
              active: true,
              label: '12:00',
              payload: [
                {
                  name: 'value',
                  value: 12,
                  dataKey: 'value',
                  payload: { fill: 'hsl(var(--color-chart-1))' },
                },
              ],
            })
          : content}
        {children}
      </div>
    ),
  }
})

const httpMocks = vi.hoisted(() => ({
  get: vi.fn(),
}))

vi.mock('@/lib/http', () => ({ backendApi: { get: httpMocks.get } }))

const breakdown: DetailedStatisticsBreakdown = {
  name: 'model-a',
  is_embedding: false,
  request_count: 2,
  input_tokens: 20,
  output_tokens: 10,
  total_tokens: 30,
  cache_hit_tokens: 15,
  cache_miss_tokens: 5,
  cache_hit_rate: 0.75,
  total_cost: 0.3,
  avg_time_cost: 1.5,
  std_time_cost: 0.5,
  avg_calls_per_reply: 1,
  avg_tokens_per_reply: 15,
  avg_tokens_per_call: 15,
}

const abnormalBreakdown: DetailedStatisticsBreakdown = {
  name: 'broken-model',
  is_embedding: false,
  request_count: 0,
  input_tokens: 0,
  output_tokens: 0,
  total_tokens: 0,
  cache_hit_tokens: 0,
  cache_miss_tokens: 0,
  cache_hit_rate: null,
  total_cost: 0,
  avg_time_cost: 0,
  std_time_cost: 0,
  avg_calls_per_reply: null,
  avg_tokens_per_reply: null,
  avg_tokens_per_call: null,
}

function makeSummary(overrides: Partial<DetailedStatisticsSummary> = {}): DetailedStatisticsSummary {
  return {
    online_time: 3600,
    total_messages: 10,
    total_replies: 2,
    total_requests: 2,
    total_tokens: 30,
    input_tokens: 20,
    output_tokens: 10,
    cache_hit_tokens: 15,
    cache_miss_tokens: 5,
    cache_hit_rate: 0.75,
    total_cost: 0.3,
    cost_per_100_messages: 3,
    cost_per_100_messages_excluding_replies: 3.75,
    cost_per_100_replies: 15,
    cost_per_hour: 0.3,
    tokens_per_hour: 30,
    ...overrides,
  }
}

function makeEmptyDistributions(): DetailedStatisticsDistributions {
  return {
    owner_tokens: [],
    model_tokens: [],
    module_tokens: [],
    request_type_tokens: [],
    chat_tokens: [],
    owner_costs: [],
    model_costs: [],
    module_costs: [],
    request_type_costs: [],
    chat_messages: [],
    chat_costs: [],
  }
}

function makePeriod(overrides: Partial<DetailedStatisticsPeriod> = {}): DetailedStatisticsPeriod {
  return {
    key: 'all_time',
    start_time: '2026-06-01T12:00:00',
    end_time: '2026-07-01T12:00:00',
    summary: makeSummary(),
    models: [breakdown],
    task_groups: [],
    modules: [{ ...breakdown, name: 'replyer' }],
    request_types: [{ ...breakdown, name: 'replyer.chat' }],
    chats: [{ name: '测试群聊', message_count: 10 }],
    distributions: {
      owner_tokens: [],
      model_tokens: [],
      module_tokens: [],
      request_type_tokens: [],
      chat_tokens: [],
      owner_costs: [{ name: '本体', value: 0.3 }],
      model_costs: [{ name: 'model-a', value: 0.3 }],
      module_costs: [{ name: 'replyer', value: 0.3 }],
      request_type_costs: [{ name: 'replyer.chat', value: 0.3 }],
      chat_messages: [{ name: '测试群聊', value: 10 }],
      chat_costs: [{ name: '测试群聊', value: 0.3 }],
    },
    ...overrides,
  }
}

function makeTrend(overrides: Partial<DetailedStatisticsTrendData> = {}): DetailedStatisticsTrendData {
  return {
    time_labels: ['12:00', '13:00'],
    total_cost_data: [0.3],
    cost_by_model: { 'model-a': [0.3] },
    cost_by_module: { replyer: [0.3] },
    message_by_chat: { 测试群聊: [10] },
    ...overrides,
  }
}

function makeMetrics(
  overrides: Partial<DetailedStatisticsMetricsData> = {}
): DetailedStatisticsMetricsData {
  return {
    time_labels: ['07-01', '07-02'],
    cost_per_100_messages: [3],
    cost_per_hour: [0.3],
    tokens_per_hour: [30],
    cost_per_100_replies: [15],
    ...overrides,
  }
}

function makeData(overrides: Partial<DetailedStatisticsData> = {}): DetailedStatisticsData {
  return {
    generated_at: '2026-07-01T12:00:00',
    periods: [makePeriod()],
    trends: {
      '24h': makeTrend(),
    },
    metrics: {
      '7d': makeMetrics(),
    },
    ...overrides,
  }
}

const detailedData = makeData()

function createDeferred<T>() {
  let resolve!: (value: T | PromiseLike<T>) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve
    reject = nextReject
  })
  return { promise, resolve, reject }
}

async function renderFreshPage() {
  cleanup()
  vi.resetModules()
  const { StatisticsPage: Page } = await import('../index')
  let view!: ReturnType<typeof render>
  await act(async () => {
    view = render(<Page />)
    await Promise.resolve()
  })
  return view
}

async function waitForPageData() {
  await waitFor(() => {
    expect(screen.getByText('总请求数')).toBeInTheDocument()
  })
}

describe('StatisticsPage', () => {
  beforeEach(() => {


    vi.mocked(backendApi.get).mockResolvedValue(detailedData)
  })

  afterEach(() => {
    cleanup()
  })

  it('加载同源详细统计并保留 HTML 报告入口', async () => {
    const user = userEvent.setup()
    render(<StatisticsPage />)

    await waitFor(() => {
      expect(screen.getAllByText('model-a').length).toBeGreaterThan(0)
    })
    expect(backendApi.get).toHaveBeenCalledWith('/api/webui/statistics/detailed')
    expect(screen.getByText('总请求数')).toBeInTheDocument()

    const htmlLink = screen.getByRole('link', { name: '打开 HTML 版' })
    expect(htmlLink).toHaveAttribute('href', '/maibot_statistics.html')
    expect(htmlLink).toHaveAttribute('target', '_blank')

    await user.click(screen.getByRole('tab', { name: '数据图表' }))
    expect(screen.getByText('总花费趋势')).toBeInTheDocument()
  })

  it('接口失败时展示错误提示', async () => {
    vi.mocked(backendApi.get).mockRejectedValue(new Error('统计接口挂了'))
    await renderFreshPage()

    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.getByText('详细统计加载失败')).toBeInTheDocument()
    expect(screen.getByText('统计接口挂了')).toBeInTheDocument()
    expect(screen.queryByText('总请求数')).not.toBeInTheDocument()
  })

  it('非 Error 失败时不展示错误页也不展示数据', async () => {
    vi.mocked(backendApi.get).mockRejectedValue('network down')
    await renderFreshPage()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '刷新' })).not.toBeDisabled()
    })
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByText('总请求数')).not.toBeInTheDocument()
    expect(document.querySelector('.animate-pulse')).toBeNull()
  })

  it('首次加载且无缓存时展示骨架屏', async () => {
    const deferred = createDeferred<DetailedStatisticsData>()
    vi.mocked(backendApi.get).mockImplementation(() => deferred.promise)

    const view = await renderFreshPage()
    expect(view.container.querySelector('.animate-pulse')).not.toBeNull()
    expect(screen.getByRole('button', { name: '刷新' })).toBeDisabled()

    await act(async () => {
      deferred.resolve(detailedData)
    })
    await waitForPageData()
    expect(view.container.querySelector('.animate-pulse')).toBeNull()
  })

  it('空分类、空聊天与空分布展示空状态，并可切换维度', async () => {
    const user = userEvent.setup()
    vi.mocked(backendApi.get).mockResolvedValue(
      makeData({
        periods: [
          makePeriod({
            models: [],
            task_groups: [],
            modules: [],
            request_types: [],
            chats: [],
            distributions: makeEmptyDistributions(),
          }),
        ],
      })
    )
    await renderFreshPage()
    await waitForPageData()

    expect(screen.getAllByText('当前统计时段暂无数据').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('tab', { name: '按模块' }))
    expect(screen.getAllByText('当前统计时段暂无数据').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('tab', { name: '按请求类型' }))
    expect(screen.getAllByText('当前统计时段暂无数据').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('tab', { name: '聊天消息' }))
    expect(screen.getAllByText('当前统计时段暂无数据').length).toBeGreaterThan(0)
  })

  it('可切换趋势时间范围与指标尺度，缺失范围展示空状态', async () => {
    const user = userEvent.setup()
    vi.mocked(backendApi.get).mockResolvedValue(
      makeData({
        trends: {
          '6h': makeTrend({ time_labels: ['06:00'] }),
          '12h': makeTrend({ time_labels: ['00:00'] }),
          '24h': makeTrend({
            cost_by_model: {},
            cost_by_module: {},
            message_by_chat: {},
          }),
        },
        metrics: {
          '7d': makeMetrics(),
          '30d': makeMetrics({ time_labels: ['06-01'] }),
        },
      })
    )
    await renderFreshPage()
    await waitForPageData()

    await user.click(screen.getByRole('tab', { name: '数据图表' }))
    expect(screen.getByText('总花费趋势')).toBeInTheDocument()
    expect(screen.getAllByText('当前统计时段暂无数据').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('button', { name: '6小时' }))
    expect(screen.getByRole('button', { name: '6小时' })).toHaveAttribute(
      'aria-pressed',
      'true'
    )
    await user.click(screen.getByRole('button', { name: '12小时' }))
    expect(screen.getByRole('button', { name: '12小时' })).toHaveAttribute(
      'aria-pressed',
      'true'
    )
    await user.click(screen.getByRole('button', { name: '48小时' }))
    expect(screen.getByText('当前统计时段暂无数据')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '24小时' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: '指标趋势' }))
    expect(screen.getByText('花费/消息数量趋势')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '30天' }))
    expect(screen.getByRole('button', { name: '30天' })).toHaveAttribute(
      'aria-pressed',
      'true'
    )
    await user.click(screen.getByRole('button', { name: '24小时' }))
    expect(screen.getByText('当前统计时段暂无数据')).toBeInTheDocument()
  })

  it('展示缓存命中率，异常 breakdown 显示 N/A，并按周期排序回退默认页签', async () => {
    const user = userEvent.setup()



    vi.mocked(backendApi.get).mockResolvedValue(
      makeData({
        periods: [
          makePeriod({
            key: 'weird_period',
            summary: makeSummary({ online_time: -8, cache_hit_rate: 0 }),
            models: [abnormalBreakdown],
            task_groups: [],
            modules: [],
            request_types: [],
            chats: [],
            distributions: {
              ...makeEmptyDistributions(),
              owner_costs: [
                { name: '来源-1', value: 1 },
                { name: '来源-2', value: 2 },
                { name: '来源-3', value: 3 },
                { name: '来源-4', value: 4 },
                { name: '来源-5', value: 5 },
                { name: '来源-6', value: 6 },
              ],
            },
          }),
          makePeriod({
            key: 'last_15_minutes',
            summary: makeSummary({
              online_time: 45,
              total_tokens: 15_000,
              total_messages: 10_000,
              cache_hit_rate: null,
              cache_hit_tokens: 0,
              cache_miss_tokens: 0,
            }),
            models: [abnormalBreakdown, { ...breakdown, name: 'model-b' }],
            chats: [{ name: '私聊用户', message_count: 12_000 }],
          }),
          makePeriod({
            key: 'last_7_days',
            summary: makeSummary({
              online_time: 90_061,
              cache_hit_rate: 0.5,
            }),
          }),
        ],
      })
    )
    await renderFreshPage()
    await waitForPageData()

    const periodTabs = screen
      .getAllByRole('tab')
      .map((tab) => tab.textContent)
    expect(periodTabs.slice(0, 5)).toEqual([
      '近7天',
      '近15分钟',
      'weird_period',
      '数据图表',
      '指标趋势',
    ])

    expect(screen.getByText('1天 1小时 1分钟')).toBeInTheDocument()
    expect(screen.getByText('50.00%')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: '近15分钟' }))
    expect(screen.getByText('45秒')).toBeInTheDocument()
    expect(screen.getByText('1.5万')).toBeInTheDocument()
    expect(screen.getByText('1万')).toBeInTheDocument()
    expect(screen.getAllByText('N/A').length).toBeGreaterThan(0)
    expect(screen.getAllByText('broken-model').length).toBeGreaterThan(0)
    expect(screen.getAllByText('0.0±0.0s').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('tab', { name: '聊天消息' }))
    expect(screen.getByText('私聊用户')).toBeInTheDocument()
    expect(screen.getByText('1.2万')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'weird_period' }))
    expect(screen.getByText('0秒')).toBeInTheDocument()
    expect(screen.getByText('0.00%')).toBeInTheDocument()
    expect(screen.getAllByText('N/A').length).toBeGreaterThan(0)

    const seriesButton = screen.getByRole('button', { name: /来源-1/ })
    expect(seriesButton).toHaveAttribute('aria-pressed', 'true')
    await user.click(seriesButton)
    expect(seriesButton).toHaveAttribute('aria-pressed', 'false')
    expect(seriesButton).toHaveClass('line-through')
    await user.click(seriesButton)
    expect(seriesButton).toHaveAttribute('aria-pressed', 'true')
  })

  it('可隐藏趋势图系列，并在刷新时再次请求接口', async () => {
    const user = userEvent.setup()
    await renderFreshPage()
    await waitForPageData()

    expect(screen.getAllByText('75.00%').length).toBeGreaterThan(0)
    expect(screen.getAllByText('缓存命中Token').length).toBeGreaterThan(0)
    expect(screen.getAllByText('缓存未命中Token').length).toBeGreaterThan(0)

    await user.click(screen.getByRole('tab', { name: '按模块' }))
    expect(screen.getAllByText('replyer').length).toBeGreaterThan(0)
    await user.click(screen.getByRole('tab', { name: '按请求类型' }))
    expect(screen.getAllByText('replyer.chat').length).toBeGreaterThan(0)
    await user.click(screen.getByRole('tab', { name: '聊天消息' }))
    const chatTable = screen.getByRole('table')
    expect(within(chatTable).getByText('测试群聊')).toBeInTheDocument()
    expect(within(chatTable).getByText('10')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: '数据图表' }))
    const seriesButton = screen.getByRole('button', { name: 'replyer' })
    expect(seriesButton).toHaveAttribute('aria-pressed', 'true')
    await user.click(seriesButton)
    expect(seriesButton).toHaveAttribute('aria-pressed', 'false')
    await user.click(seriesButton)
    expect(seriesButton).toHaveAttribute('aria-pressed', 'true')

    vi.mocked(backendApi.get).mockClear()
    vi.mocked(backendApi.get).mockResolvedValue(detailedData)
    await user.click(screen.getByRole('button', { name: '刷新' }))
    await waitFor(() => {
      expect(backendApi.get).toHaveBeenCalledWith('/api/webui/statistics/detailed')
    })
  })

  it('模块缓存命中时立即展示已有数据，刷新过程不再出现骨架屏', async () => {
    await renderFreshPage()
    await waitForPageData()
    cleanup()

    const deferred = createDeferred<DetailedStatisticsData>()
    vi.mocked(backendApi.get).mockImplementation(() => deferred.promise)
    const { StatisticsPage: CachedPage } = await import('../index')
    let view!: ReturnType<typeof render>
    await act(async () => {
      view = render(<CachedPage />)
      await Promise.resolve()
    })

    expect(screen.getByText('总请求数')).toBeInTheDocument()
    expect(screen.getAllByText('75.00%').length).toBeGreaterThan(0)
    expect(view.container.querySelector('.animate-pulse')).toBeNull()
    expect(screen.getByRole('button', { name: '刷新' })).toBeDisabled()

    await act(async () => {
      deferred.resolve(detailedData)
    })
    await waitFor(() => {
      expect(screen.getByRole('button', { name: '刷新' })).not.toBeDisabled()
    })
  })

  it('没有周期数据时回退到趋势页签', async () => {
    vi.mocked(backendApi.get).mockResolvedValue(
      makeData({
        periods: [],
        trends: {},
        metrics: {},
      })
    )
    await renderFreshPage()

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: '数据图表' })).toHaveAttribute(
        'data-state',
        'active'
      )
    })
    expect(screen.getByText('当前统计时段暂无数据')).toBeInTheDocument()
    expect(screen.getByText(/^统计截止时间：/)).toBeInTheDocument()
  })
})
