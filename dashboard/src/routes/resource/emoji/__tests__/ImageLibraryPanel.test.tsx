import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { ImageLibraryPanel } from '../ImageLibraryPanel'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  upload: vi.fn(),
  tags: vi.fn(),
  adopt: vi.fn(),
  remove: vi.fn(),
  scan: vi.fn(),
  toast: vi.fn(),
}))

vi.mock('@/lib/emoji-api', () => ({
  getLibraryImages: mocks.list,
  getLibraryImageUrl: (id: string, original = false) =>
    `/images/${id}${original ? '?original=true' : ''}`,
  uploadLibraryImage: mocks.upload,
  updateLibraryTags: mocks.tags,
  adoptLibraryImage: mocks.adopt,
  deleteLibraryImage: mocks.remove,
  syncImageLibrary: mocks.scan,
  retryLibraryTags: vi.fn(),
}))
vi.mock('@/hooks/use-toast', () => ({ useToast: () => ({ toast: mocks.toast }) }))
vi.mock('@/lib/api-base', () => ({ resolveApiPath: async (url: string) => url }))
vi.mock('@/components/emoji-thumbnail', () => ({
  EmojiThumbnail: ({ alt }: { alt: string }) => <span>{alt}</span>,
}))
vi.mock('@/components/image-gallery', () => ({
  ImageGalleryProvider: ({ children }: { children: React.ReactNode }) => children,
  useImageGallery: () => ({ open: vi.fn() }),
}))

const image = {
  id: 'abc',
  filename: '开心.gif',
  manual_tags: ['手动'],
  auto_tags: ['表情包'],
  tags: ['手动', '表情包'],
  caption_status: 'done',
}

function renderPanel(props = {}) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <ImageLibraryPanel {...props} />
    </QueryClientProvider>
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({
    items: [image],
    total: 1,
    pending: 0,
    failed: 0,
    directory: '/data/images',
  })
})

describe('ImageLibraryPanel', () => {
  it('sends the selected original item through the chat callback', async () => {
    const choose = vi.fn().mockResolvedValue(undefined)
    renderPanel({ compact: true, onChoose: choose })
    fireEvent.click(await screen.findByRole('button', { name: '发送' }))
    await waitFor(() => expect(choose).toHaveBeenCalledWith(image))
    expect(mocks.adopt).not.toHaveBeenCalled()
  })

  it('edits manual tags and adds the same image to native emojis', async () => {
    renderPanel()
    fireEvent.click(await screen.findByRole('button', { name: '标签' }))
    expect(screen.getByRole('textbox', { name: '手动标签' })).toHaveValue('手动')
    fireEvent.change(screen.getByRole('textbox', { name: '手动标签' }), {
      target: { value: '开心' },
    })
    fireEvent.click(screen.getByRole('button', { name: '保存' }))
    await waitFor(() => expect(mocks.tags).toHaveBeenCalledWith('abc', '开心'))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: '据为己用' }))
    await waitFor(() => expect(mocks.adopt).toHaveBeenCalledWith('abc'))
  })

  it('shows scan errors and requires confirmation to delete the file', async () => {
    mocks.scan.mockResolvedValue({
      added: 0,
      existing: 1,
      removed: 0,
      errors: [{ file: 'bad.png', error: '无法读取图片内容' }],
    })
    renderPanel()
    fireEvent.click(await screen.findByRole('button', { name: '扫描目录' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('bad.png：无法读取图片内容')
    fireEvent.click(screen.getByRole('button', { name: '删除' }))
    expect(mocks.remove).not.toHaveBeenCalled()
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '删除' }))
    await waitFor(() => expect(mocks.remove).toHaveBeenCalledWith('abc'))
  })
})
