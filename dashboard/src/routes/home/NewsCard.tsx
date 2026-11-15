import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { ExternalLink, Newspaper, Package, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'

import { removeTopLevelHeadings } from '@/components/update-notice-markdown'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { MarkdownRenderer } from '@/components/markdown-renderer'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import type { NewsItem } from '@/lib/news-api'
import { getUpdateHistory, type UpdateHistoryEntry } from '@/lib/system-api'
import { cn } from '@/lib/utils'

const RELATIVE_TIME_DAY_THRESHOLD = 30

/** 资讯相关链接可使用站内插件地址，不依赖用户部署 WebUI 的域名。 */
function getNewsPluginId(url: string): string | null {
  if (!url.startsWith('/plugins?')) return null
  return new URLSearchParams(url.slice('/plugins?'.length)).get('pluginId')?.trim() || null
}

/** 资讯发布时间相对当前时间的展示（如「2小时前」），超过 30 天回退为日期。 */
function formatRelativeTime(value: string, locale: string): string {
  const publishedTime = new Date(value).getTime()
  if (Number.isNaN(publishedTime)) return ''

  const diffSeconds = Math.round((publishedTime - Date.now()) / 1000)
  const absoluteSeconds = Math.abs(diffSeconds)
  if (absoluteSeconds >= RELATIVE_TIME_DAY_THRESHOLD * 24 * 60 * 60) {
    return new Date(publishedTime).toLocaleDateString(locale)
  }

  const formatter = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' })
  if (absoluteSeconds < 60) return formatter.format(diffSeconds, 'second')
  if (absoluteSeconds < 60 * 60) return formatter.format(Math.round(diffSeconds / 60), 'minute')
  if (absoluteSeconds < 24 * 60 * 60) return formatter.format(Math.round(diffSeconds / 3600), 'hour')
  return formatter.format(Math.round(diffSeconds / 86400), 'day')
}

export function RecentUpdatesCard() {
  const { t } = useTranslation()
  const [selectedUpdate, setSelectedUpdate] = useState<UpdateHistoryEntry | null>(null)
  const { data, error, isPending, isFetching, refetch } = useQuery({
    queryKey: ['home', 'recent-updates'],
    queryFn: () => getUpdateHistory(0, 3),
    staleTime: 10 * 60_000,
  })

  return (
    <>
      <Card className="flex h-full min-h-0 flex-col">
        <CardHeader className="flex flex-row items-center justify-between gap-2 pb-3">
          <CardTitle className="flex items-center gap-2 text-sm font-medium">
            <Newspaper className="h-4 w-4" />
            {t('home.updates.title')}
          </CardTitle>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7"
            aria-label={t('home.updates.refresh')}
            title={t('home.updates.refresh')}
            disabled={isFetching}
            onClick={() => void refetch()}
          >
            <RefreshCw className={cn('h-3.5 w-3.5', isFetching && 'animate-spin')} />
          </Button>
        </CardHeader>
        <CardContent className="flex min-h-0 flex-1 flex-col">
          {isPending ? (
            <div className="flex min-h-0 flex-1 flex-col justify-center space-y-2">
              {[0, 1, 2].map((index) => (
                <div key={index} className="rounded-md border p-2.5">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="mt-1.5 h-3 w-full" />
                </div>
              ))}
            </div>
          ) : error && !data ? (
            <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 text-sm">
              <span className="text-destructive">{error.message}</span>
              <Button variant="outline" size="sm" onClick={() => void refetch()}>
                <RefreshCw className="mr-2 h-4 w-4" />
                {t('home.news.retry')}
              </Button>
            </div>
          ) : data && data.entries.length > 0 ? (
            <ScrollArea className="min-h-0 flex-1 pr-3">
              <div className="space-y-2">
                {data.entries.map((entry) => {
                  const summary = entry.content
                    .split(/\r?\n/)
                    .filter((line) => /^-\s+/.test(line))
                    .slice(0, 3)
                    .map((line) => line.replace(/^-\s+/, '').replace(/`/g, '').split(/[。；]/, 1)[0])
                    .join('；')

                  return (
                    <button
                      key={entry.version}
                      type="button"
                      title={t('home.updates.open')}
                      className="hover:bg-accent/40 block w-full rounded-md border p-2.5 text-left transition-colors focus-visible:ring-2 focus-visible:outline-none"
                      onClick={() => setSelectedUpdate(entry)}
                    >
                      <span className="block text-sm font-medium">{entry.title.replace(/^#\s+/, '')}</span>
                      <span className="text-muted-foreground mt-1 line-clamp-2 text-xs leading-relaxed">
                        {summary}
                      </span>
                    </button>
                  )
                })}
              </div>
            </ScrollArea>
          ) : (
            <div className="text-muted-foreground flex min-h-0 flex-1 items-center justify-center text-sm">
              {t('home.updates.empty')}
            </div>
          )}
        </CardContent>
      </Card>
      <Dialog open={selectedUpdate !== null} onOpenChange={(open) => !open && setSelectedUpdate(null)}>
        <DialogContent className="[--dialog-width:48rem]">
          {selectedUpdate && (
            <>
              <DialogHeader>
                <DialogTitle className="pr-6">{selectedUpdate.title.replace(/^#\s+/, '')}</DialogTitle>
                <DialogDescription>{t('home.updates.details')}</DialogDescription>
              </DialogHeader>
              <DialogBody>
                <MarkdownRenderer content={removeTopLevelHeadings(selectedUpdate.content)} />
              </DialogBody>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}

export function NewsDialog({ selectedNews, onClose }: { selectedNews: NewsItem | null; onClose: () => void }) {
  const { t, i18n } = useTranslation()
  const locale = i18n.resolvedLanguage || i18n.language
  const selectedPluginId = selectedNews ? getNewsPluginId(selectedNews.url) : null

  return (
    <Dialog open={selectedNews !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="[--dialog-width:48rem]">
        {selectedNews && (
          <>
            <DialogHeader>
              <DialogTitle className="pr-6">{selectedNews.title}</DialogTitle>
              <DialogDescription>
                {[selectedNews.pinned ? t('home.news.pinned') : '', selectedNews.source, formatRelativeTime(selectedNews.published_at, locale)]
                  .filter(Boolean)
                  .join(' · ')}
              </DialogDescription>
            </DialogHeader>
            <DialogBody>
              <MarkdownRenderer content={selectedNews.content || selectedNews.summary} />
            </DialogBody>
            {selectedNews.url && (
              <div className="flex justify-end">
                <Button asChild variant="outline" size="sm">
                  {selectedPluginId ? (
                    <Link
                      to="/plugins"
                      search={{ pluginId: selectedPluginId }}
                      onClick={onClose}
                    >
                      <Package className="mr-2 h-4 w-4" />
                      {t('home.news.openPlugin')}
                    </Link>
                  ) : (
                    <a href={selectedNews.url} target="_blank" rel="noopener noreferrer">
                      <ExternalLink className="mr-2 h-4 w-4" />
                      {t('home.news.openLink')}
                    </a>
                  )}
                </Button>
              </div>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  )
}
