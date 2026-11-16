import { useMemo, useState, type ComponentProps } from 'react'
import { AlertCircle, CalendarClock, ExternalLink, RefreshCw } from 'lucide-react'

import { CartesianGrid, Cell, Line, LineChart, Pie, PieChart, XAxis, YAxis } from 'recharts'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from '@/components/ui/chart'
import { DashboardTabBar, DashboardTabTrigger } from '@/components/ui/dashboard-tabs'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'

import type {
  DetailedDistributionItem,
  DetailedStatisticsBreakdown,
  DetailedStatisticsData,
  DetailedStatisticsMetricsData,
  DetailedStatisticsPeriod,
  DetailedStatisticsTrendData,
} from './types'
import { useDetailedStatistics } from './useDetailedStatistics'

const STATISTICSPAGE_TABLE_LABELS: Record<string, string> = {
  "name": "名称",
  "requests": "调用次数",
  "inputTokens": "输入Token",
  "outputTokens": "输出Token",
  "totalTokens": "Token总量",
  "cacheHitTokens": "缓存命中Token",
  "cacheMissTokens": "缓存未命中Token",
  "cacheHitRate": "缓存命中率",
  "cost": "累计花费",
  "time": "耗时",
  "callsPerReply": "每次回复平均调用次数",
  "tokensPerReply": "每次回复平均Token",
  "tokensPerCall": "每次调用平均Token",
  "chat": "联系人/群组名称",
  "messages": "消息数量",
}

const STATISTICSPAGE_DISTRIBUTIONS_LABELS: Record<string, string> = {
  "metric": "统计指标",
  "costs": "花费",
  "tokens": "Token",
  "ownerTokens": "调用来源Token分布",
  "modelTokens": "模型Token分布",
  "moduleTokens": "模块Token分布",
  "requestTypeTokens": "请求类型Token分布",
  "chatTokens": "聊天流Token分布",
  "ownerCosts": "调用来源花费分布",
  "modelCosts": "模型花费分布",
  "moduleCosts": "模块花费分布",
  "requestTypeCosts": "请求类型花费分布",
  "chatMessages": "聊天消息分布",
  "chatCosts": "聊天流花费分布",
}

const STATISTICSPAGE_RANGES_LABELS: Record<string, string> = {
  "6h": "6小时",
  "12h": "12小时",
  "24h": "24小时",
  "48h": "48小时",
  "7d": "7天",
  "30d": "30天",
}

const STATISTICSPAGE_PERIODS_LABELS: Record<string, string> = {
  "all_time": "自部署以来",
  "last_30_days": "近30天",
  "last_7_days": "近7天",
  "last_3_days": "近3天",
  "last_24_hours": "近1天",
  "last_3_hours": "近3小时",
  "last_hour": "近1小时",
  "last_15_minutes": "近15分钟",
}


const PERIOD_KEYS = [
  'all_time',
  'last_30_days',
  'last_7_days',
  'last_3_days',
  'last_24_hours',
  'last_3_hours',
  'last_hour',
  'last_15_minutes',
] as const

const CHART_COLORS = [
  'hsl(var(--color-chart-1))',
  'hsl(var(--color-chart-2))',
  'hsl(var(--color-chart-3))',
  'hsl(var(--color-chart-4))',
  'hsl(var(--color-chart-5))',
]

function formatNumber(value: number, locale: string, maximumFractionDigits = 2): string {
  return new Intl.NumberFormat(locale, {
    notation: Math.abs(value) >= 10_000 ? 'compact' : 'standard',
    maximumFractionDigits,
  }).format(value)
}

function formatCurrency(value: number, locale: string, digits = 2): string {
  return `¥${new Intl.NumberFormat(locale, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value)}`
}

function formatPercent(value: number | null): string {
  return value === null ? 'N/A' : `${(value * 100).toFixed(2)}%`
}

function formatOptionalNumber(value: number | null, locale: string): string {
  return value === null ? 'N/A' : formatNumber(value, locale)
}

function formatDuration(seconds: number, locale: string): string {
  const totalSeconds = Math.max(0, Math.floor(seconds))
  const days = Math.floor(totalSeconds / 86400)
  const hours = Math.floor((totalSeconds % 86400) / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const remainingSeconds = totalSeconds % 60
  const parts: string[] = []
  const formatUnit = (value: number, unit: 'day' | 'hour' | 'minute' | 'second') =>
    new Intl.NumberFormat(locale, {
      style: 'unit',
      unit,
      unitDisplay: 'narrow',
      maximumFractionDigits: 0,
    }).format(value)

  if (days > 0) parts.push(formatUnit(days, 'day'))
  if (hours > 0 || days > 0) parts.push(formatUnit(hours, 'hour'))
  if (minutes > 0 || hours > 0 || days > 0) parts.push(formatUnit(minutes, 'minute'))
  if (parts.length === 0) parts.push(formatUnit(remainingSeconds, 'second'))
  return parts.join(' ')
}

function formatDateTime(value: string, locale: string): string {
  return new Date(value).toLocaleString(locale, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

type StatisticsTooltipContentProps = ComponentProps<typeof ChartTooltipContent> & {
  valueKind: 'currency' | 'count'
  locale: string
}

/** 统一本页图表提示框：关闭位移动画改用淡入，并同时展示条目名与格式化后的数值 */
function StatisticsTooltipContent({
  valueKind,
  locale,
  className,
  ...props
}: StatisticsTooltipContentProps) {
  const formatValue = (value: number | string) =>
    valueKind === 'currency'
      ? formatCurrency(Number(value), locale)
      : formatNumber(Number(value), locale)

  return (
    <ChartTooltipContent
      {...props}
      className={cn('animate-fade-in max-w-64', className)}
      formatter={(value, name, item) => (
        <>
          <span
            className="h-2.5 w-2.5 shrink-0 rounded-xs"
            style={{ backgroundColor: item.payload.fill ?? item.color }}
          />
          <div className="flex min-w-0 flex-1 items-center justify-between gap-3 leading-none">
            <span className="text-muted-foreground wrap-break-word">{name}</span>
            <span className="text-foreground shrink-0 font-mono font-medium tabular-nums">
              {formatValue(value)}
            </span>
          </div>
        </>
      )}
    />
  )
}

function StatisticsPageSkeleton() {
  return (
    <div className="space-y-5 rounded-xl border p-4 sm:p-5" aria-hidden="true">
      <Skeleton className="h-11 w-full" />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 2xl:grid-cols-6">
        {Array.from({ length: 16 }, (_, index) => (
          <Skeleton key={index} className="h-28" />
        ))}
      </div>
      <Skeleton className="h-90 w-full" />
    </div>
  )
}

interface MetricItemProps {
  label: string
  value: string
  detail?: string
}

function MetricItem({ label, value, detail }: MetricItemProps) {
  return (
    <Card
      data-colorful-item="true"
      className="group hover:border-primary/60 relative min-h-28 min-w-0 overflow-hidden px-4 py-4 transition-[border-color,box-shadow,transform] duration-200 hover:-translate-y-0.5"
    >
      <div data-colorful-fill="true" className="bg-primary/75 absolute inset-x-0 top-0 h-0.5" />
      <div className="text-muted-foreground truncate text-xs font-medium tracking-wide">
        {label}
      </div>
      <div
        data-colorful-value="true"
        className="text-primary mt-2 truncate text-xl font-bold tracking-tight tabular-nums"
      >
        {value}
      </div>
      {detail && <div className="text-muted-foreground mt-2 truncate text-[11px]">{detail}</div>}
    </Card>
  )
}

function SummaryMetrics({ period, locale }: { period: DetailedStatisticsPeriod; locale: string }) {
  const summary = period.summary
  const items: MetricItemProps[] = [
    {
      label: '总在线时间',
      value: formatDuration(summary.online_time, locale),
    },
    {
      label: '总消息数',
      value: formatNumber(summary.total_messages, locale),
    },
    {
      label: '总回复数',
      value: formatNumber(summary.total_replies, locale),
    },
    {
      label: '总请求数',
      value: formatNumber(summary.total_requests, locale),
    },
    {
      label: '总Token数',
      value: formatNumber(summary.total_tokens, locale),
    },
    {
      label: '总输入Token',
      value: formatNumber(summary.input_tokens, locale),
    },
    {
      label: '总输出Token',
      value: formatNumber(summary.output_tokens, locale),
    },
    {
      label: 'Prompt缓存命中率',
      value: formatPercent(summary.cache_hit_rate),
    },
    {
      label: '缓存命中Token',
      value: formatNumber(summary.cache_hit_tokens, locale),
    },
    {
      label: '缓存未命中Token',
      value: formatNumber(summary.cache_miss_tokens, locale),
    },
    {
      label: '总花费',
      value: formatCurrency(summary.total_cost, locale),
    },
    {
      label: '花费/消息数量',
      value: formatCurrency(summary.cost_per_100_messages, locale, 4),
      detail: '每100条',
    },
    {
      label: '花费/接收消息数量',
      value: formatCurrency(summary.cost_per_100_messages_excluding_replies, locale, 4),
      detail: '每100条',
    },
    {
      label: '花费/回复数量',
      value: formatCurrency(summary.cost_per_100_replies, locale, 4),
      detail: '每100条',
    },
    {
      label: '花费/时间',
      value: formatCurrency(summary.cost_per_hour, locale),
      detail: '每小时',
    },
    {
      label: 'Token/时间',
      value: formatNumber(summary.tokens_per_hour, locale),
      detail: '每小时',
    },
  ]

  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 2xl:grid-cols-6">
      {items.map((item) => (
        <MetricItem key={item.label} {...item} />
      ))}
    </div>
  )
}

function BreakdownTable({ rows, locale, embedding = false }: {
  rows: DetailedStatisticsBreakdown[]
  locale: string
  embedding?: boolean
}) {

  if (rows.length === 0) {
    return <EmptyState />
  }

  return (
    <>
      <div className="space-y-3 sm:hidden">
        {rows.map((row) => {
          const metrics = [
            { key: 'requests', value: formatNumber(row.request_count, locale), primary: true },
            { key: 'totalTokens', value: formatNumber(row.total_tokens, locale), primary: true },
            { key: 'cost', value: formatCurrency(row.total_cost, locale), primary: true },
            { key: 'inputTokens', value: formatNumber(row.input_tokens, locale), primary: embedding },
            { key: 'outputTokens', value: formatNumber(row.output_tokens, locale) },
            { key: 'cacheHitTokens', value: formatNumber(row.cache_hit_tokens, locale) },
            { key: 'cacheMissTokens', value: formatNumber(row.cache_miss_tokens, locale) },
            { key: 'cacheHitRate', value: formatPercent(row.cache_hit_rate) },
            { key: 'time', value: `${row.avg_time_cost.toFixed(1)}±${row.std_time_cost.toFixed(1)}s` },
            { key: 'callsPerReply', value: formatOptionalNumber(row.avg_calls_per_reply, locale) },
            { key: 'tokensPerReply', value: formatOptionalNumber(row.avg_tokens_per_reply, locale) },
            { key: 'tokensPerCall', value: formatOptionalNumber(row.avg_tokens_per_call, locale) },
          ].filter((metric) => !embedding || [
            'requests', 'inputTokens', 'cost', 'time', 'tokensPerCall',
          ].includes(metric.key))
          const renderMetrics = (primary: boolean) => (
            <dl className="grid grid-cols-2 gap-x-3 gap-y-3 text-sm">
              {metrics.filter((metric) => Boolean(metric.primary) === primary).map((metric) => (
                <div key={metric.key} className="min-w-0">
                  <dt className="text-muted-foreground text-xs">{STATISTICSPAGE_TABLE_LABELS[metric.key]}</dt>
                  <dd className="mt-1 wrap-break-word font-medium tabular-nums">{metric.value}</dd>
                </div>
              ))}
            </dl>
          )
          return (
            <div key={row.name} className="min-w-0 rounded-md border p-3">
              <details>
                <summary className="cursor-pointer text-sm font-semibold wrap-anywhere">
                  {row.name}
                </summary>
                <div className="mt-3 border-t border-dashed pt-3">{renderMetrics(false)}</div>
              </details>
              <div className="mt-3">{renderMetrics(true)}</div>
            </div>
          )
        })}
      </div>
    <div className="hidden overflow-hidden rounded-md border sm:block">
      <Table className={embedding ? 'min-w-175' : 'min-w-365'}>
        <TableHeader className="bg-muted/60">
          <TableRow>
            <TableHead
              data-statistics-sticky-cell="true"
              className="bg-muted sticky left-0 z-10 min-w-32 font-semibold sm:min-w-52"
            >
              {'名称'}
            </TableHead>
            <TableHead>{'调用次数'}</TableHead>
            <TableHead>{'输入Token'}</TableHead>
            {!embedding && (
              <>
                <TableHead>{'输出Token'}</TableHead>
                <TableHead>{'Token总量'}</TableHead>
                <TableHead>{'缓存命中Token'}</TableHead>
                <TableHead>{'缓存未命中Token'}</TableHead>
                <TableHead>{'缓存命中率'}</TableHead>
              </>
            )}
            <TableHead>{'累计花费'}</TableHead>
            <TableHead>{'耗时'}</TableHead>
            {!embedding && (
              <>
                <TableHead>{'每次回复平均调用次数'}</TableHead>
                <TableHead>{'每次回复平均Token'}</TableHead>
              </>
            )}
            <TableHead>{'每次调用平均Token'}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row) => (
            <TableRow key={row.name}>
              <TableCell
                data-statistics-sticky-cell="true"
                className="bg-card sticky left-0 z-10 max-w-40 truncate font-medium sm:max-w-64"
                title={row.name}
              >
                {row.name}
              </TableCell>
              <TableCell>{formatNumber(row.request_count, locale)}</TableCell>
              <TableCell>{formatNumber(row.input_tokens, locale)}</TableCell>
              {!embedding && (
                <>
                  <TableCell>{formatNumber(row.output_tokens, locale)}</TableCell>
                  <TableCell>{formatNumber(row.total_tokens, locale)}</TableCell>
                  <TableCell>{formatNumber(row.cache_hit_tokens, locale)}</TableCell>
                  <TableCell>{formatNumber(row.cache_miss_tokens, locale)}</TableCell>
                  <TableCell>{formatPercent(row.cache_hit_rate)}</TableCell>
                </>
              )}
              <TableCell>{formatCurrency(row.total_cost, locale)}</TableCell>
              <TableCell className="whitespace-nowrap">
                {row.avg_time_cost.toFixed(1)}±{row.std_time_cost.toFixed(1)}s
              </TableCell>
              {!embedding && (
                <>
                  <TableCell>{formatOptionalNumber(row.avg_calls_per_reply, locale)}</TableCell>
                  <TableCell>{formatOptionalNumber(row.avg_tokens_per_reply, locale)}</TableCell>
                </>
              )}
              <TableCell>{formatOptionalNumber(row.avg_tokens_per_call, locale)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
    </>
  )
}

function ChatTable({ period, locale }: { period: DetailedStatisticsPeriod; locale: string }) {
  if (period.chats.length === 0) {
    return <EmptyState />
  }
  return (
    <div className="overflow-hidden rounded-md border">
      <Table>
        <TableHeader className="bg-muted/60">
          <TableRow>
            <TableHead>{'联系人/群组名称'}</TableHead>
            <TableHead className="whitespace-nowrap text-right sm:w-44">{'消息数量'}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {period.chats.map((chat) => (
            <TableRow key={chat.name}>
              <TableCell className="font-medium wrap-anywhere">{chat.name}</TableCell>
              <TableCell className="text-right tabular-nums">
                {formatNumber(chat.message_count, locale)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="text-muted-foreground flex min-h-40 items-center justify-center text-sm">
      {'当前统计时段暂无数据'}
    </div>
  )
}

function SplitBreakdownTable({ rows, locale }: { rows: DetailedStatisticsBreakdown[]; locale: string }) {
  const embeddingRows = rows.filter((row) => row.is_embedding)
  const otherRows = rows.filter((row) => !row.is_embedding)
  return (
    <div className="space-y-4">
      {(otherRows.length > 0 || embeddingRows.length === 0) && (
        <BreakdownTable rows={otherRows} locale={locale} />
      )}
      {embeddingRows.length > 0 && (
        <section className="space-y-3">
          <h3 className="text-sm font-semibold">{'嵌入统计'}</h3>
          <BreakdownTable rows={embeddingRows} locale={locale} embedding />
        </section>
      )}
    </div>
  )
}

function DetailTables({ period, locale }: { period: DetailedStatisticsPeriod; locale: string }) {
  return (
    <Card className="border-l-primary overflow-hidden border-l-4 shadow-sm">
      <CardHeader className="border-b pb-4">
        <CardTitle className="text-lg">{'分类统计'}</CardTitle>
      </CardHeader>
      <CardContent className="pt-4 sm:pt-4">
        <Tabs defaultValue="models">
          <TabsList
            className="border-border/70 bg-muted/40 mb-4 h-auto w-full justify-start overflow-x-auto overflow-y-hidden rounded-md border px-1 py-2 [&>button]:shrink-0"
            style={{ touchAction: 'pan-x pan-y' }}
          >
            <TabsTrigger value="models">{'按模型'}</TabsTrigger>
            <TabsTrigger value="taskGroups">{'按任务组'}</TabsTrigger>
            <TabsTrigger value="modules">{'按模块'}</TabsTrigger>
            <TabsTrigger value="requestTypes">
              {'按请求类型'}
            </TabsTrigger>
            <TabsTrigger value="chats">{'聊天消息'}</TabsTrigger>
          </TabsList>
          <TabsContent value="models" className="mt-0">
            <SplitBreakdownTable rows={period.models} locale={locale} />
          </TabsContent>
          <TabsContent value="taskGroups" className="mt-0">
            <SplitBreakdownTable rows={period.task_groups} locale={locale} />
          </TabsContent>
          <TabsContent value="modules" className="mt-0">
            <SplitBreakdownTable rows={period.modules} locale={locale} />
          </TabsContent>
          <TabsContent value="requestTypes" className="mt-0">
            <SplitBreakdownTable rows={period.request_types} locale={locale} />
          </TabsContent>
          <TabsContent value="chats" className="mt-0">
            <ChatTable period={period} locale={locale} />
          </TabsContent>
        </Tabs>
      </CardContent>
    </Card>
  )
}

function DistributionChart({
  title,
  data,
  valueKind,
  locale,
}: {
  title: string
  data: DetailedDistributionItem[]
  valueKind: 'currency' | 'count'
  locale: string
}) {
  const [hiddenNames, setHiddenNames] = useState<Set<string>>(() => new Set())
  const chartData = data.map((item, index) => ({
    ...item,
    fill: CHART_COLORS[index % CHART_COLORS.length],
  }))
  const visibleData = chartData.filter((item) => !hiddenNames.has(item.name))
  const config = Object.fromEntries(
    chartData.map((item, index) => [`item_${index}`, { label: item.name, color: item.fill }])
  ) as ChartConfig

  const toggleName = (name: string) => {
    setHiddenNames((current) => {
      const next = new Set(current)
      if (next.has(name)) next.delete(name)
      else next.add(name)
      return next
    })
  }

  const formatValue = (value: number | string) =>
    valueKind === 'currency'
      ? formatCurrency(Number(value), locale)
      : formatNumber(Number(value), locale)

  return (
    <Card className="min-w-0 overflow-hidden shadow-sm">
      <CardHeader className="border-b pb-3 max-sm:px-2! max-sm:py-2!">
        <CardTitle className="text-sm max-sm:text-xs! max-sm:wrap-break-word sm:truncate" title={title}>
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-4 max-sm:p-2! sm:pt-4">
        {data.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
            <ChartContainer
              config={config}
              className="aspect-auto h-37.5 w-full min-w-0 sm:h-85 sm:flex-1"
            >
              <PieChart>
                {/* 关闭 recharts 默认的位移过渡，改用提示框内容淡入 */}
                <ChartTooltip
                  isAnimationActive={false}
                  content={<StatisticsTooltipContent valueKind={valueKind} locale={locale} />}
                />
                <Pie
                  data={visibleData}
                  dataKey="value"
                  nameKey="name"
                  innerRadius="52%"
                  outerRadius="88%"
                  paddingAngle={1}
                  isAnimationActive={false}
                >
                  {visibleData.map((item) => (
                    <Cell key={item.name} fill={item.fill} />
                  ))}
                </Pie>
              </PieChart>
            </ChartContainer>
            <div className="grid max-h-28 shrink-0 grid-cols-1 content-start gap-1 overflow-y-auto sm:max-h-85 sm:w-44 lg:w-52">
              {chartData.map((item) => {
                const hidden = hiddenNames.has(item.name)
                return (
                  <button
                    key={item.name}
                    type="button"
                    aria-pressed={!hidden}
                    className={cn(
                      'hover:bg-muted grid min-w-0 grid-cols-[10px_minmax(0,1fr)] items-center gap-x-1 gap-y-0.5 rounded-md px-1 py-1 text-left text-xs transition-colors sm:flex sm:gap-2 sm:px-2',
                      hidden && 'text-muted-foreground line-through opacity-60'
                    )}
                    onClick={() => toggleName(item.name)}
                    title={`显示或隐藏 ${item.name}`}
                  >
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-sm"
                      style={{ backgroundColor: item.fill }}
                    />
                    <span className="min-w-0 flex-1 truncate">{item.name}</span>
                    <span className="col-start-2 shrink-0 tabular-nums">{formatValue(item.value)}</span>
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}

function DistributionGrid({
  period,
  locale,
}: {
  period: DetailedStatisticsPeriod
  locale: string
}) {
  const [metric, setMetric] = useState<'costs' | 'tokens'>('costs')
  const valueKind = metric === 'costs' ? 'currency' : 'count'
  const charts = [
    [
      STATISTICSPAGE_DISTRIBUTIONS_LABELS[metric === 'costs' ? 'ownerCosts' : 'ownerTokens'],
      period.distributions[`owner_${metric}`],
      valueKind,
    ],
    [
      STATISTICSPAGE_DISTRIBUTIONS_LABELS[metric === 'costs' ? 'modelCosts' : 'modelTokens'],
      period.distributions[`model_${metric}`],
      valueKind,
    ],
    [
      STATISTICSPAGE_DISTRIBUTIONS_LABELS[metric === 'costs' ? 'moduleCosts' : 'moduleTokens'],
      period.distributions[`module_${metric}`],
      valueKind,
    ],
    [
      STATISTICSPAGE_DISTRIBUTIONS_LABELS[metric === 'costs' ? 'requestTypeCosts' : 'requestTypeTokens'],
      period.distributions[`request_type_${metric}`],
      valueKind,
    ],
    ['聊天消息分布', period.distributions.chat_messages, 'count'],
    [
      STATISTICSPAGE_DISTRIBUTIONS_LABELS[metric === 'costs' ? 'chatCosts' : 'chatTokens'],
      period.distributions[`chat_${metric}`],
      valueKind,
    ],
  ] as const

  return (
    <section className="space-y-4">
      <div className="border-border flex flex-wrap items-center gap-3 border-b pb-3">
        <span className="bg-primary h-6 w-1 rounded-full" aria-hidden="true" />
        <h2 className="text-lg font-semibold">{'数据分布图表'}</h2>
        <div
          className="ml-auto flex gap-1"
          role="group"
          aria-label={'统计指标'}
        >
          {(['costs', 'tokens'] as const).map((value) => (
            <Button
              key={value}
              size="sm"
              variant={metric === value ? 'secondary' : 'ghost'}
              aria-pressed={metric === value}
              onClick={() => setMetric(value)}
            >
              {STATISTICSPAGE_DISTRIBUTIONS_LABELS[value]}
            </Button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-1 sm:gap-4 xl:grid-cols-2">
        {charts.map(([title, data, valueKind]) => (
          <DistributionChart
            key={title}
            title={title}
            data={data}
            valueKind={valueKind}
            locale={locale}
          />
        ))}
      </div>
    </section>
  )
}

function PeriodPanel({ period, locale }: { period: DetailedStatisticsPeriod; locale: string }) {
  return (
    <div className="space-y-5">
      <div className="border-border/80 bg-muted/35 flex items-center gap-3 rounded-md border px-4 py-3">
        <CalendarClock className="text-primary size-4 shrink-0" aria-hidden="true" />
        <div className="text-muted-foreground text-xs font-medium">
          {`统计时段：${formatDateTime(period.start_time, locale)} 至 ${formatDateTime(period.end_time, locale)}`}
        </div>
      </div>
      <SummaryMetrics period={period} locale={locale} />
      <DetailTables period={period} locale={locale} />
      <DistributionGrid period={period} locale={locale} />
    </div>
  )
}

interface SeriesDefinition {
  key: string
  label: string
  values: number[]
  color: string
}

function MultiSeriesChart({
  title,
  labels,
  series,
  valueKind,
  locale,
}: {
  title: string
  labels: string[]
  series: Record<string, number[]>
  valueKind: 'currency' | 'count'
  locale: string
}) {
  const [hiddenKeys, setHiddenKeys] = useState<Set<string>>(() => new Set())
  const definitions: SeriesDefinition[] = Object.entries(series).map(([label, values], index) => ({
    key: `series_${index}`,
    label,
    values,
    color: CHART_COLORS[index % CHART_COLORS.length],
  }))
  const chartData = labels.map((label, index) => {
    const item: Record<string, string | number> = { label }
    for (const definition of definitions) {
      item[definition.key] = definition.values[index] ?? 0
    }
    return item
  })
  const config = Object.fromEntries(
    definitions.map((definition) => [
      definition.key,
      { label: definition.label, color: definition.color },
    ])
  ) as ChartConfig

  return (
    <Card className="overflow-hidden shadow-sm">
      <CardHeader className="border-b pb-3">
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="pt-4 sm:pt-4">
        {definitions.length === 0 ? (
          <EmptyState />
        ) : (
          <>
            <ChartContainer config={config} className="aspect-auto h-85 w-full min-w-0">
              <LineChart data={chartData} margin={{ left: 8, right: 8, top: 8 }}>
                <CartesianGrid vertical={false} strokeDasharray="3 3" />
                <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={24} />
                <YAxis
                  tickLine={false}
                  axisLine={false}
                  width={64}
                  tickFormatter={(value) =>
                    valueKind === 'currency'
                      ? formatCurrency(Number(value), locale)
                      : formatNumber(Number(value), locale)
                  }
                />
                <ChartTooltip
                  isAnimationActive={false}
                  content={<StatisticsTooltipContent valueKind={valueKind} locale={locale} />}
                />
                {definitions.map((definition) => (
                  <Line
                    key={definition.key}
                    dataKey={definition.key}
                    name={definition.label}
                    stroke={definition.color}
                    strokeWidth={2}
                    dot={false}
                    hide={hiddenKeys.has(definition.key)}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ChartContainer>
            <div className="mt-2 flex max-h-24 flex-wrap gap-1 overflow-y-auto">
              {definitions.map((definition) => {
                const hidden = hiddenKeys.has(definition.key)
                return (
                  <button
                    key={definition.key}
                    type="button"
                    aria-pressed={!hidden}
                    className={cn(
                      'hover:bg-muted inline-flex max-w-60 items-center gap-1.5 rounded-md px-2 py-1 text-xs transition-colors',
                      hidden && 'text-muted-foreground line-through opacity-60'
                    )}
                    onClick={() =>
                      setHiddenKeys((current) => {
                        const next = new Set(current)
                        if (next.has(definition.key)) next.delete(definition.key)
                        else next.add(definition.key)
                        return next
                      })
                    }
                    title={`显示或隐藏 ${definition.label}`}
                  >
                    <span
                      className="h-2 w-2 shrink-0 rounded-sm"
                      style={{ backgroundColor: definition.color }}
                    />
                    <span className="truncate">{definition.label}</span>
                  </button>
                )
              })}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  )
}

function SingleSeriesChart({
  title,
  labels,
  values,
  valueKind,
  locale,
}: {
  title: string
  labels: string[]
  values: number[]
  valueKind: 'currency' | 'count'
  locale: string
}) {
  const data = labels.map((label, index) => ({ label, value: values[index] ?? 0 }))
  const config = { value: { label: title, color: CHART_COLORS[0] } } satisfies ChartConfig
  return (
    <Card className="overflow-hidden shadow-sm">
      <CardHeader className="border-b pb-3">
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className="pt-4 sm:pt-4">
        <ChartContainer config={config} className="aspect-auto h-80 w-full min-w-0">
          <LineChart data={data} margin={{ left: 8, right: 8, top: 8 }}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            <XAxis dataKey="label" tickLine={false} axisLine={false} minTickGap={24} />
            <YAxis
              tickLine={false}
              axisLine={false}
              width={64}
              tickFormatter={(value) =>
                valueKind === 'currency'
                  ? formatCurrency(Number(value), locale)
                  : formatNumber(Number(value), locale)
              }
            />
            <ChartTooltip
              isAnimationActive={false}
              content={<StatisticsTooltipContent valueKind={valueKind} locale={locale} />}
            />
            <Line
              dataKey="value"
              name={title}
              stroke="var(--color-value)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  )
}

function TotalCostChart({ data, locale }: { data: DetailedStatisticsTrendData; locale: string }) {
  return (
    <SingleSeriesChart
      title={'总花费趋势'}
      labels={data.time_labels}
      values={data.total_cost_data}
      valueKind="currency"
      locale={locale}
    />
  )
}

function TrendsPanel({ data, locale }: { data: DetailedStatisticsData; locale: string }) {
  const [range, setRange] = useState('24h')
  const trendData = data.trends[range]
  if (!trendData) return <EmptyState />

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold">{'数据图表'}</h2>
        <div className="flex flex-wrap gap-1" aria-label={'时间范围'}>
          {['6h', '12h', '24h', '48h'].map((value) => (
            <Button
              key={value}
              type="button"
              size="sm"
              variant={range === value ? 'secondary' : 'outline'}
              aria-pressed={range === value}
              onClick={() => setRange(value)}
            >
              {STATISTICSPAGE_RANGES_LABELS[value]}
            </Button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4">
        <TotalCostChart data={trendData} locale={locale} />
        <MultiSeriesChart
          title={'各模块花费趋势'}
          labels={trendData.time_labels}
          series={trendData.cost_by_module}
          valueKind="currency"
          locale={locale}
        />
        <MultiSeriesChart
          title={'各模型花费趋势'}
          labels={trendData.time_labels}
          series={trendData.cost_by_model}
          valueKind="currency"
          locale={locale}
        />
        <MultiSeriesChart
          title={'各聊天流消息数趋势'}
          labels={trendData.time_labels}
          series={trendData.message_by_chat}
          valueKind="count"
          locale={locale}
        />
      </div>
    </div>
  )
}

function MetricsPanel({ data, locale }: { data: DetailedStatisticsData; locale: string }) {
  const [range, setRange] = useState('7d')
  const metrics = data.metrics[range] as DetailedStatisticsMetricsData | undefined
  if (!metrics) return <EmptyState />

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-base font-semibold">{'指标趋势'}</h2>
        <div className="flex flex-wrap gap-1" aria-label={'时间尺度'}>
          {['24h', '7d', '30d'].map((value) => (
            <Button
              key={value}
              type="button"
              size="sm"
              variant={range === value ? 'secondary' : 'outline'}
              aria-pressed={range === value}
              onClick={() => setRange(value)}
            >
              {STATISTICSPAGE_RANGES_LABELS[value]}
            </Button>
          ))}
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4">
        <SingleSeriesChart
          title={'花费/消息数量趋势'}
          labels={metrics.time_labels}
          values={metrics.cost_per_100_messages}
          valueKind="currency"
          locale={locale}
        />
        <SingleSeriesChart
          title={'花费/时间趋势'}
          labels={metrics.time_labels}
          values={metrics.cost_per_hour}
          valueKind="currency"
          locale={locale}
        />
        <SingleSeriesChart
          title={'Token/时间趋势'}
          labels={metrics.time_labels}
          values={metrics.tokens_per_hour}
          valueKind="count"
          locale={locale}
        />
        <SingleSeriesChart
          title={'花费/回复数量趋势'}
          labels={metrics.time_labels}
          values={metrics.cost_per_100_replies}
          valueKind="currency"
          locale={locale}
        />
      </div>
    </div>
  )
}

function getOrderedPeriods(data: DetailedStatisticsData): DetailedStatisticsPeriod[] {
  const order = new Map(PERIOD_KEYS.map((key, index) => [key, index]))
  return [...data.periods].sort(
    (left, right) =>
      (order.get(left.key as (typeof PERIOD_KEYS)[number]) ?? 99) -
      (order.get(right.key as (typeof PERIOD_KEYS)[number]) ?? 99)
  )
}

export function StatisticsPage() {
  const locale = 'zh-CN'
  const { data, error, loading, refresh } = useDetailedStatistics()
  const periods = useMemo(() => (data ? getOrderedPeriods(data) : []), [data])
  const [activeTab, setActiveTab] = useState('last_7_days')
  const validTabValues = new Set([...periods.map((period) => period.key), 'trends', 'metrics'])
  const selectedTab = validTabValues.has(activeTab) ? activeTab : (periods[0]?.key ?? 'trends')

  return (
    <div className="flex min-h-full flex-col p-4 sm:p-6">
      <div className="mx-auto w-full max-w-450">
        <header className="border-primary/30 bg-card relative mb-5 overflow-hidden rounded-xl border p-5 shadow-sm sm:p-6">
          <div className="bg-primary absolute inset-y-0 left-0 w-1.5" aria-hidden="true" />
          <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
            <div className="min-w-0">
              <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
                {'详细统计数据'}
              </h1>
              <div className="bg-primary mt-3 h-0.5 w-28" aria-hidden="true" />
              <p className="text-muted-foreground mt-3 max-w-2xl text-sm sm:text-base">
                {'查看麦麦运行期间的模型调用、Token、费用、消息与在线时长。'}
              </p>
            </div>
            <div className="flex shrink-0 flex-col items-start gap-3 sm:items-end">
              {data && (
                <div className="border-border/80 bg-muted/35 rounded-md border px-3 py-2 text-xs font-medium tabular-nums">
                  {`统计截止时间：${formatDateTime(data.generated_at, locale)}`}
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => void refresh()}
                  disabled={loading}
                >
                  <RefreshCw className={cn(loading && 'animate-spin')} />
                  {'刷新'}
                </Button>
                <Button asChild variant="outline" size="sm">
                  <a href="/maibot_statistics.html" target="_blank" rel="noopener noreferrer">
                    <ExternalLink />
                    {'打开 HTML 版'}
                  </a>
                </Button>
              </div>
            </div>
          </div>
        </header>

        {error && !data ? (
          <Alert variant="destructive">
            <AlertCircle />
            <AlertTitle>{'详细统计加载失败'}</AlertTitle>
            <AlertDescription>{error || '请稍后重试'}</AlertDescription>
          </Alert>
        ) : loading && !data ? (
          <StatisticsPageSkeleton />
        ) : data ? (
          <Tabs
            value={selectedTab}
            onValueChange={setActiveTab}
            className="border-primary/25 bg-card/40 min-w-0 rounded-xl border p-3 shadow-sm sm:p-5"
          >
            <DashboardTabBar className="border-border/70 bg-muted/45 rounded-md border">
              {periods.map((period) => (
                <DashboardTabTrigger key={period.key} value={period.key}>
                  {STATISTICSPAGE_PERIODS_LABELS[period.key] ?? period.key}
                </DashboardTabTrigger>
              ))}
              <DashboardTabTrigger value="trends">
                {'数据图表'}
              </DashboardTabTrigger>
              <DashboardTabTrigger value="metrics">
                {'指标趋势'}
              </DashboardTabTrigger>
            </DashboardTabBar>

            {periods.map((period) => (
              <TabsContent key={period.key} value={period.key} className="mt-5">
                <PeriodPanel period={period} locale={locale} />
              </TabsContent>
            ))}
            <TabsContent value="trends" className="mt-5">
              <TrendsPanel data={data} locale={locale} />
            </TabsContent>
            <TabsContent value="metrics" className="mt-5">
              <MetricsPanel data={data} locale={locale} />
            </TabsContent>
          </Tabs>
        ) : null}
      </div>
    </div>
  )
}
