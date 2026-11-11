import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus, RefreshCw } from 'lucide-react'

import { ImageGalleryProvider, useImageGallery } from '@/components/image-gallery'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { DataPagination } from '@/components/ui/data-pagination'
import { Input } from '@/components/ui/input'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useToast } from '@/hooks/use-toast'
import { resolveApiPath } from '@/lib/api-base'
import {
  adoptLibraryImage,
  deleteLibraryImage,
  getLibraryImages,
  getLibraryImageUrl,
  retryLibraryTags,
  syncImageLibrary,
  updateLibraryTags,
  uploadLibraryImage,
  type LibraryImage,
} from '@/lib/emoji-api'

function PreviewButton({
  item,
  src,
  hasError,
}: {
  item: LibraryImage
  src?: string
  hasError: boolean
}) {
  const gallery = useImageGallery()
  const [failedSrc, setFailedSrc] = useState<string>()
  return (
    <button
      type="button"
      className="aspect-square w-full overflow-hidden rounded-lg p-1"
      aria-label={`预览 ${item.filename}`}
      onClick={() =>
        gallery?.open({
          src: getLibraryImageUrl(item.id, true),
          alt: item.filename,
          authenticated: true,
        })
      }
    >
      {hasError || (src !== undefined && failedSrc === src) ? (
        '图片加载失败'
      ) : src !== undefined ? (
        <img
          src={src}
          alt={item.filename}
          loading="lazy"
          decoding="async"
          className="bg-muted h-full w-full object-contain"
          onError={() => setFailedSrc(src)}
        />
      ) : (
        <Loader2 className="mx-auto animate-spin" />
      )}
    </button>
  )
}

export function ImageLibraryPanel({
  compact = false,
  onChoose,
  browserHeader,
}: {
  compact?: boolean
  onChoose?: (item: LibraryImage) => Promise<void>
  browserHeader?: ReactNode
}) {
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(compact ? 12 : 24)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState<LibraryImage | null>(null)
  const [deleting, setDeleting] = useState<LibraryImage[] | null>(null)
  const [tags, setTags] = useState('')
  const [scanErrors, setScanErrors] = useState<{ file: string; error: string }[]>([])
  const inputRef = useRef<HTMLInputElement>(null)
  const client = useQueryClient()
  const { toast } = useToast()
  const previewBase = useQuery({
    queryKey: ['gallery-preview-base-url'],
    queryFn: () => resolveApiPath(''),
  })
  const query = useQuery({
    queryKey: ['image-gallery', page, search, pageSize],
    queryFn: () => getLibraryImages(page, search, pageSize),
    refetchInterval: 10_000,
  })
  const data = query.data
  const selectedItems = data?.items.filter((item) => selectedIds.has(item.id)) || []
  const allSelected = !!data?.items.length && selectedItems.length === data.items.length
  const managing = !compact && !onChoose
  useEffect(() => {
    if (data && page > Math.max(1, Math.ceil(data.total / pageSize))) {
      setPage(Math.max(1, Math.ceil(data.total / pageSize)))
      setSelectedIds(new Set())
    }
  }, [data, page, pageSize])

  const perform = async (action: () => Promise<unknown>, message: string) => {
    setBusy(true)
    try {
      await action()
      toast({ title: message })
    } catch (error) {
      toast({
        title: '图库操作失败',
        description: error instanceof Error ? error.message : String(error),
        variant: 'destructive',
      })
    } finally {
      await client.invalidateQueries({ queryKey: ['image-gallery'] })
      await client.invalidateQueries({ queryKey: ['emoji'] })
      setBusy(false)
    }
  }

  const performBatch = (items: LibraryImage[], action: 'adopt' | 'delete') =>
    perform(
      async () => {
        const completed: string[] = []
        const errors: string[] = []
        for (const item of items) {
          try {
            if (action === 'adopt') await adoptLibraryImage(item.id)
            else await deleteLibraryImage(item.id)
            completed.push(item.id)
          } catch (error) {
            errors.push(
              `${item.filename}：${error instanceof Error ? error.message : String(error)}`
            )
          }
        }
        setSelectedIds((current) => new Set([...current].filter((id) => !completed.includes(id))))
        if (action === 'delete') setDeleting(null)
        if (errors.length) {
          throw new Error(
            `成功 ${completed.length} 张，失败 ${errors.length} 张\n${errors.join('\n')}`
          )
        }
      },
      action === 'adopt' ? `已将 ${items.length} 张图片加入可发送表情包` : '图库图片已删除'
    )

  return (
    <div className={`flex min-h-0 flex-col gap-3 ${compact ? '' : 'h-full p-3 sm:p-4'}`}>
      {browserHeader}
      {!compact && data && (
        <div className="text-muted-foreground space-y-1 text-xs">
          <p>
            共 {data.total} 张 · 待识别 {data.pending} 张 · 识别失败 {data.failed} 张
          </p>
          <p className="break-all">目录：{data.directory}</p>
          <p>
            支持子目录、文件名标签和自动标签；在聊天中请求“从图库找图”即可使用。自动收图在表情包配置中开启。
          </p>
          <p>自动标签使用“功能分配 → 图像识别”；未配置模型时保留待识别状态。</p>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <Input
          value={search}
          disabled={busy}
          onChange={(event) => {
            setSearch(event.target.value)
            setPage(1)
            setSelectedIds(new Set())
          }}
          placeholder="搜索图库标签或文件名"
          aria-label="搜索图库"
          className="min-w-0 flex-1"
        />
        {!compact && (
          <>
            <Button
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() => inputRef.current?.click()}
            >
              <Plus />
              上传
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={busy}
              onClick={() =>
                void perform(async () => {
                  const report = await syncImageLibrary()
                  setScanErrors(report.errors)
                }, '图库扫描完成')
              }
            >
              <RefreshCw />
              扫描目录
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={busy || !data?.failed}
              onClick={() => void perform(retryLibraryTags, '已安排重试失败标签')}
            >
              重试识别
            </Button>
            <input
              ref={inputRef}
              className="hidden"
              type="file"
              multiple
              accept="image/jpeg,image/png,image/gif,image/webp,image/bmp"
              onChange={(event) => {
                const files = Array.from(event.target.files || [])
                event.target.value = ''
                if (files.length)
                  void perform(async () => {
                    for (const file of files) await uploadLibraryImage(file)
                  }, '图库图片已上传')
              }}
            />
          </>
        )}
      </div>
      {managing && (
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-2 text-xs">
            <Checkbox
              aria-label="全选本页"
              checked={allSelected ? true : selectedItems.length > 0 ? 'indeterminate' : false}
              disabled={busy || !data?.items.length}
              onCheckedChange={(checked) =>
                setSelectedIds(new Set(checked === true ? data?.items.map((item) => item.id) : []))
              }
            />
            全选本页
          </label>
          <span className="text-muted-foreground mr-auto text-xs" aria-live="polite">
            已选择 {selectedItems.length} 张
          </span>
          <Button
            variant="ghost"
            size="sm"
            disabled={busy || !selectedItems.length}
            onClick={() => setSelectedIds(new Set())}
          >
            取消选择
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={busy || !selectedItems.length}
            onClick={() => void performBatch(selectedItems, 'adopt')}
          >
            批量据为己用
          </Button>
          <Button
            variant="destructive"
            size="sm"
            disabled={busy || !selectedItems.length}
            onClick={() => setDeleting(selectedItems)}
          >
            批量删除
          </Button>
        </div>
      )}
      {scanErrors.length > 0 && (
        <div role="alert" className="text-destructive max-h-24 overflow-auto text-xs">
          {scanErrors.map((error) => (
            <p key={error.file}>
              {error.file}：{error.error}
            </p>
          ))}
        </div>
      )}
      {query.isError ? (
        <div role="alert" className="text-destructive text-sm">
          {query.error.message}
          <Button variant="ghost" onClick={() => void query.refetch()}>
            重试
          </Button>
        </div>
      ) : query.isPending ? (
        <Loader2 className="mx-auto animate-spin" />
      ) : (
        <ImageGalleryProvider
          images={(data?.items || []).map((item) => ({
            src: getLibraryImageUrl(item.id, true),
            alt: item.filename,
            authenticated: true,
          }))}
        >
          <div className={`min-h-0 overflow-y-auto ${compact ? 'max-h-72' : 'flex-1'}`}>
            <div
              className={`grid gap-3 ${compact ? 'grid-cols-3' : 'grid-cols-3 md:grid-cols-4 xl:grid-cols-6'}`}
            >
              {data?.items.map((item) => (
                <div
                  key={item.id}
                  className="bg-card relative min-w-0 rounded-lg border p-2"
                  data-list-selected={selectedIds.has(item.id) ? 'true' : undefined}
                >
                  {managing && (
                    <Checkbox
                      aria-label={`选择 ${item.filename}`}
                      checked={selectedIds.has(item.id)}
                      disabled={busy}
                      className="bg-background absolute top-3 right-3 z-10"
                      onCheckedChange={(checked) =>
                        setSelectedIds((current) => {
                          const next = new Set(current)
                          if (checked === true) next.add(item.id)
                          else next.delete(item.id)
                          return next
                        })
                      }
                    />
                  )}
                  <PreviewButton
                    item={item}
                    src={
                      previewBase.data === undefined
                        ? undefined
                        : `${previewBase.data}${getLibraryImageUrl(item.id)}`
                    }
                    hasError={previewBase.isError}
                  />
                  <p className="truncate text-xs" title={item.filename}>
                    {item.filename}
                  </p>
                  <p
                    className="text-muted-foreground mt-1 line-clamp-2 text-xs"
                    title={item.tags.join('、')}
                  >
                    {item.tags.join('、') || '暂无标签'}
                  </p>
                  {!compact && (
                    <p className="text-muted-foreground mt-1 text-xs">
                      {
                        { pending: '待识别', done: '已识别', failed: '识别失败' }[
                          item.caption_status
                        ]
                      }
                    </p>
                  )}
                  <div className="mt-2 flex flex-wrap gap-1">
                    {onChoose ? (
                      <Button
                        size="xs"
                        disabled={busy}
                        onClick={() => void perform(() => onChoose(item), '已发送图库图片')}
                      >
                        发送
                      </Button>
                    ) : (
                      <>
                        <Button
                          size="xs"
                          variant="outline"
                          disabled={busy}
                          onClick={() =>
                            void perform(() => adoptLibraryImage(item.id), '已加入可发送表情包')
                          }
                        >
                          据为己用
                        </Button>
                        <Button
                          size="xs"
                          variant="ghost"
                          disabled={busy}
                          onClick={() => {
                            setEditing(item)
                            setTags(item.manual_tags.join('、'))
                          }}
                        >
                          标签
                        </Button>
                        <Button
                          size="xs"
                          variant="ghost"
                          disabled={busy}
                          onClick={() => setDeleting([item])}
                        >
                          删除
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
            {data?.items.length === 0 && (
              <p className="text-muted-foreground py-8 text-center text-sm">
                暂无匹配图片，可上传图片或扫描图库目录。
              </p>
            )}
          </div>
        </ImageGalleryProvider>
      )}
      <DataPagination
        total={data?.total || 0}
        page={page}
        pageSize={pageSize}
        onPageChange={(nextPage) => {
          setPage(nextPage)
          setSelectedIds(new Set())
        }}
        onPageSizeChange={(size) => {
          setPageSize(size)
          setPage(1)
          setSelectedIds(new Set())
        }}
        pageSizeOptions={[12, 24, 48, 100]}
        disabled={busy}
      />
      <Dialog
        open={editing !== null}
        onOpenChange={(open) => {
          if (!open) setEditing(null)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>编辑图库标签</DialogTitle>
            <DialogDescription>
              手动标签与自动标签分别保存，多个标签用逗号或顿号分隔。
            </DialogDescription>
          </DialogHeader>
          <Input
            aria-label="手动标签"
            value={tags}
            onChange={(event) => setTags(event.target.value)}
          />
          <DialogFooter>
            <Button
              disabled={busy}
              onClick={() =>
                editing &&
                void perform(async () => {
                  await updateLibraryTags(editing.id, tags)
                  setEditing(null)
                }, '标签已保存')
              }
            >
              保存
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog
        open={deleting !== null}
        onOpenChange={(open) => {
          if (!open && !busy) setDeleting(null)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {deleting && deleting.length > 1 ? '批量删除图库图片' : '删除图库图片'}
            </DialogTitle>
            <DialogDescription>
              将删除 {deleting?.length}{' '}
              张图库图片的文件和标签，操作不可撤销；已据为己用的表情包副本会保留。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" disabled={busy} onClick={() => setDeleting(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              disabled={busy}
              onClick={() => deleting && void performBatch(deleting, 'delete')}
            >
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
