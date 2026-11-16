import { useCallback, useEffect, useState } from 'react'
import type { ReactNode } from 'react'


import { useFeatureFlags } from '@/hooks/use-feature-flags'
import { Link } from '@tanstack/react-router'

import { Button } from '@/components/ui/button'
import { PageFrame } from '@/components/ui/surface'
import { downloadFile, listFileChats, listFiles, readFileText, removeFile, sendFile, uploadFile } from '@/lib/files-api'
import type { FileChat, FileList, FileText, StoredFile } from '@/lib/files-api'

const FILES_STATE_LABELS: Record<string, string> = {
  "remote": "未下载",
  "ready": "已就绪",
  "failed": "失败",
  "uploading": "上传中",
  "downloading": "下载中",
}

const FILES_DELIVERY_LABELS: Record<string, string> = {
  "sent": "文件已发送",
  "unknown": "投递结果不确定，请核对聊天后再决定是否重发。",
}


const bytes = (size: number) => `${(size / 1024 ** 2).toFixed(2)} MiB`

export function FilesPage({ headerActions }: { headerActions?: ReactNode }) {
  const { flags, error: configError } = useFeatureFlags()
  const filesEnabled = flags?.files === true
  const [data, setData] = useState<FileList>()
  const [chats, setChats] = useState<FileChat[]>([])
  const [chat, setChat] = useState('')
  const [offset, setOffset] = useState(0)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [preview, setPreview] = useState<{ file: StoredFile; content: FileText }>()
  const [encoding, setEncoding] = useState('utf-8-sig')
  const refresh = useCallback(async () => {
    if (!filesEnabled) return
    const [listing, sessions] = await Promise.all([listFiles(chat || undefined, offset), listFileChats()])
    setData(listing); setChats(sessions)
  }, [chat, offset, filesEnabled])
  useEffect(() => { refresh().catch(e => setError(String(e))) }, [refresh])
  async function run(action: () => Promise<unknown>) {
    setBusy(true); setError(''); setNotice('')
    try { await action(); await refresh() } catch (e) { setError(String(e)) } finally { setBusy(false) }
  }
  async function showText(file: StoredFile, start = 0) {
    setPreview({ file, content: await readFileText(file.file_ref, start, encoding) })
  }
  const pageHeader = (
    <div className="flex items-center justify-between gap-4">
      <h1 className="min-w-0 text-xl font-semibold">{'文件'}</h1>
      {headerActions}
    </div>
  )
  if (!filesEnabled) return <PageFrame className="p-4 space-y-3">
    {pageHeader}
    <p role={configError ? 'alert' : 'status'}>{configError || (flags ? '文件功能已关闭，请在「能力」中开启。' : '加载中...')}</p>
    {flags && <Link to="/config/bot" className="underline">{'打开能力设置'}</Link>}
  </PageFrame>
  return <PageFrame className="p-4 space-y-4">
    {pageHeader}
    <p className="text-sm text-muted-foreground">{'附件按聊天归属管理，按需下载；文本可预览，本地上传和生成的原件保留到手动删除。'}</p>
    {data && <p className="text-sm">{'已用空间'}: {bytes(data.usage.used_bytes)} / {bytes(data.usage.max_bytes)} · {'预留空间'}: {bytes(data.usage.reserved_bytes)} · {'单文件上限'}: {bytes(data.usage.max_file_bytes)}</p>}
    <div className="flex flex-wrap gap-2 items-center">
      <select aria-label={'聊天'} className="rounded border bg-background p-2 max-w-full" value={chat}
        onChange={e => { setChat(e.target.value); setOffset(0) }}>
        <option value="">{'全部聊天'}</option>
        {chats.map(item => <option key={item.session_id} value={item.session_id}>{item.name}</option>)}
      </select>
      <Button disabled={busy} variant="outline" onClick={() => run(refresh)}>{'刷新'}</Button>
      <label className="text-sm">{'文本编码'}
        <select className="ml-2 border rounded bg-background p-2" value={encoding} onChange={e => setEncoding(e.target.value)}>
          {['utf-8-sig', 'utf-8', 'utf-16', 'gb18030'].map(value => <option key={value}>{value}</option>)}
        </select>
      </label>
      <label className="text-sm">{'上传文件'}
        <input className="block max-w-full" type="file" disabled={busy || !chat} onChange={e => {
          const file = e.target.files?.[0]; e.target.value = ''
          if (file) void run(() => uploadFile(file, chat))
        }} />
      </label>
    </div>
    {!chat && <p className="text-sm text-muted-foreground">{'先选择一个聊天，再上传文件。'}</p>}
    {error && <p role="alert" className="text-destructive whitespace-pre-wrap">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    <div className="space-y-2">{data?.items.map(file => <article key={file.file_ref} className="rounded border p-3 space-y-2">
      <div className="font-medium break-all">{file.name} <span className="font-normal text-muted-foreground">{bytes(file.size)}</span></div>
      <p className="text-sm text-muted-foreground">{(FILES_STATE_LABELS[file.state] ?? file.state)} · {(file.origin === 'remote' ? '平台缓存' : '本地原件')} · {file.chats?.map(c => c.name).join('、')}</p>
      {file.error && <p className="text-sm text-destructive">{file.error}</p>}
      <div className="flex gap-2 flex-wrap">
        <Button size="sm" variant="outline" disabled={busy} onClick={() => run(() => downloadFile(file))}>{'下载'}</Button>
        {/\.(txt|md|markdown|csv|json)$/i.test(file.name) && <Button size="sm" variant="outline" disabled={busy} onClick={() => run(() => showText(file))}>{'阅读文本'}</Button>}
        <select aria-label={'发送到聊天…'} className="border rounded bg-background max-w-full text-sm" disabled={busy} value="" onChange={e => {
          const target = e.target.value
          if (target && window.confirm(`确认将文件发送到「${chats.find(c => c.session_id === target)?.name}」？`))
            void run(async () => { const result = await sendFile(file.file_ref, target); setNotice(FILES_DELIVERY_LABELS[result.status]) })
        }}>
          <option value="">{'发送到聊天…'}</option>
          {chats.map(c => <option key={c.session_id} value={c.session_id}>{c.name}</option>)}
        </select>
        {file.origin === 'remote' && file.state === 'ready' && <Button size="sm" variant="outline" disabled={busy} onClick={() => run(() => removeFile(file.file_ref, true))}>{'清理缓存'}</Button>}
        <Button size="sm" variant="destructive" disabled={busy} onClick={() => {
          if (window.confirm(`确认删除「${file.name}」？本地原件无法恢复。`)) void run(() => removeFile(file.file_ref, false))
        }}>{'删除'}</Button>
      </div>
    </article>)}</div>
    {data?.items.length === 0 && <p>{'暂无附件'}</p>}
    <div className="flex gap-2">
      <Button disabled={busy || offset === 0} variant="outline" onClick={() => setOffset(Math.max(0, offset - 50))}>{'上一页'}</Button>
      <Button disabled={busy || (data?.items.length ?? 0) < 50} variant="outline" onClick={() => setOffset(offset + 50)}>{'下一页'}</Button>
    </div>
    {preview && <section className="rounded border p-3 space-y-2">
      <h2 className="font-semibold break-all">{preview.file.name}</h2>
      <p className="text-sm">{preview.content.offset}–{preview.content.next_offset} / {preview.content.total_characters}</p>
      <Button variant="outline" disabled={busy} onClick={() => run(() => showText(preview.file))}>{'刷新'}</Button>
      <pre className="whitespace-pre-wrap break-all max-h-96 overflow-auto bg-muted p-3 text-sm">{preview.content.text}</pre>
      <Button variant="outline" disabled={busy || preview.content.next_offset >= preview.content.total_characters}
        onClick={() => run(() => showText(preview.file, preview.content.next_offset))}>{'下一页'}</Button>
      <Button variant="ghost" onClick={() => setPreview(undefined)}>{'关闭'}</Button>
    </section>}
  </PageFrame>
}
