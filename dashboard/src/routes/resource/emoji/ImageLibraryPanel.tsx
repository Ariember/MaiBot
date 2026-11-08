import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus, RefreshCw } from 'lucide-react'

import { EmojiThumbnail } from '@/components/emoji-thumbnail'
import { ImageGalleryProvider, useImageGallery } from '@/components/image-gallery'
import { Button } from '@/components/ui/button'
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

function PreviewButton({ item }: { item: LibraryImage }) {
  const gallery = useImageGallery()
  const thumbnail = useQuery({
    queryKey: ['gallery-thumbnail-url', item.id],
    queryFn: () => resolveApiPath(getLibraryImageUrl(item.id)),
  })
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
      {thumbnail.data ? (
        <EmojiThumbnail
          src={thumbnail.data}
          alt={item.filename}
          className="h-full w-full object-contain"
        />
      ) : thumbnail.isError ? (
        '图片加载失败'
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
  const [busy, setBusy] = useState(false)
  const [editing, setEditing] = useState<LibraryImage | null>(null)
  const [deleting, setDeleting] = useState<LibraryImage | null>(null)
  const [tags, setTags] = useState('')
  const [scanErrors, setScanErrors] = useState<{ file: string; error: string }[]>([])
  const inputRef = useRef<HTMLInputElement>(null)
  const client = useQueryClient()
  const { toast } = useToast()
  const pageSize = compact ? 12 : 24
  const query = useQuery({
    queryKey: ['image-gallery', page, search, pageSize],
    queryFn: () => getLibraryImages(page, search, pageSize),
    refetchInterval: 10_000,
  })
  const data = query.data
  useEffect(() => {
    if (data && page > Math.max(1, Math.ceil(data.total / pageSize))) {
      setPage(Math.max(1, Math.ceil(data.total / pageSize)))
    }
  }, [data, page, pageSize])

  const perform = async (action: () => Promise<unknown>, message: string) => {
    setBusy(true)
    try {
      await action()
      await client.invalidateQueries({ queryKey: ['image-gallery'] })
      await client.invalidateQueries({ queryKey: ['emoji'] })
      toast({ title: message })
    } catch (error) {
      toast({
        title: '图库操作失败',
        description: error instanceof Error ? error.message : String(error),
        variant: 'destructive',
      })
    } finally {
      setBusy(false)
    }
  }

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
          onChange={(event) => {
            setSearch(event.target.value)
            setPage(1)
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
                <div key={item.id} className="bg-card min-w-0 rounded-lg border p-2">
                  <PreviewButton item={item} />
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
                          onClick={() => setDeleting(item)}
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
        onPageChange={setPage}
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
          if (!open) setDeleting(null)
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>删除图库图片</DialogTitle>
            <DialogDescription>
              将删除图库中的文件和标签；已据为己用的表情包副本会保留。
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleting(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              disabled={busy}
              onClick={() =>
                deleting &&
                void perform(async () => {
                  await deleteLibraryImage(deleting.id)
                  setDeleting(null)
                }, '图库图片已删除')
              }
            >
              删除
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
