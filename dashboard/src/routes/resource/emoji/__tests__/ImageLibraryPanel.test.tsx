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
  resolvePath: vi.fn(),
  open: vi.fn(),
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
vi.mock('@/lib/api-base', () => ({ resolveApiPath: mocks.resolvePath }))
vi.mock('@/components/image-gallery', () => ({
  ImageGalleryProvider: ({ children }: { children: React.ReactNode }) => children,
  useImageGallery: () => ({ open: mocks.open }),
}))

const image = {
  id: 'abc',
  filename: '开心.gif',
  manual_tags: ['手动'],
  auto_tags: ['表情包'],
  tags: ['手动', '表情包'],
  caption_status: 'done',
}

const otherImage = { ...image, id: 'def', filename: '第二张.png' }
const libraryResponse = {
  items: [image],
  total: 1,
  pending: 0,
  failed: 0,
  directory: '/data/images',
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
  mocks.list.mockResolvedValue(libraryResponse)
  mocks.adopt.mockResolvedValue(undefined)
  mocks.remove.mockResolvedValue(undefined)
  mocks.resolvePath.mockImplementation(async (url: string) => url)
})

describe('ImageLibraryPanel', () => {
  it('sends the selected original item through the chat callback', async () => {
    const choose = vi.fn().mockResolvedValue(undefined)
    renderPanel({ compact: true, onChoose: choose })
    fireEvent.click(await screen.findByRole('button', { name: '发送' }))
    await waitFor(() => expect(choose).toHaveBeenCalledWith(image))
    expect(mocks.adopt).not.toHaveBeenCalled()
    expect(mocks.list).toHaveBeenCalledWith(1, '', 12)
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '批量删除' })).not.toBeInTheDocument()
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

  it('changes page size from a later page and clears the page selection', async () => {
    mocks.list.mockResolvedValue({ ...libraryResponse, total: 100 })
    renderPanel()
    await screen.findByRole('checkbox', { name: '选择 开心.gif' })
    fireEvent.click(screen.getByRole('button', { name: '下一页' }))
    await waitFor(() => expect(mocks.list).toHaveBeenLastCalledWith(2, '', 24))
    fireEvent.click(await screen.findByRole('checkbox', { name: '选择 开心.gif' }))
    expect(screen.getByRole('checkbox', { name: '选择 开心.gif' })).toBeChecked()

    fireEvent.keyDown(screen.getByRole('combobox', { name: '每页' }), { key: 'Enter' })
    expect((await screen.findAllByRole('option')).map((option) => option.textContent)).toEqual([
      '12',
      '24',
      '48',
      '100',
    ])
    fireEvent.keyDown(screen.getByRole('option', { name: '48' }), { key: 'Enter' })

    await waitFor(() => expect(mocks.list).toHaveBeenLastCalledWith(1, '', 48))
    expect(await screen.findByRole('checkbox', { name: '选择 开心.gif' })).not.toBeChecked()
    expect(screen.getByRole('combobox', { name: '每页' })).toHaveTextContent('48')
  })

  it('adopts only selected images and clears successful selections', async () => {
    mocks.list.mockResolvedValue({ ...libraryResponse, items: [image, otherImage], total: 2 })
    renderPanel()
    fireEvent.click(await screen.findByRole('checkbox', { name: '选择 第二张.png' }))
    fireEvent.click(screen.getByRole('button', { name: '批量据为己用' }))

    await waitFor(() => expect(mocks.adopt).toHaveBeenCalledExactlyOnceWith('def'))
    await waitFor(() =>
      expect(screen.getByRole('checkbox', { name: '选择 第二张.png' })).not.toBeChecked()
    )
    expect(mocks.list.mock.calls.length).toBeGreaterThan(1)
  })

  it('selects the current page and confirms before deleting selected files', async () => {
    mocks.list.mockResolvedValue({ ...libraryResponse, items: [image, otherImage], total: 2 })
    renderPanel()
    await screen.findByRole('checkbox', { name: '选择 开心.gif' })
    fireEvent.click(screen.getByRole('checkbox', { name: '全选本页' }))
    expect(screen.getByRole('checkbox', { name: '选择 开心.gif' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: '选择 第二张.png' })).toBeChecked()
    fireEvent.click(screen.getByRole('button', { name: '批量删除' }))
    expect(screen.getByRole('dialog')).toHaveTextContent('2')
    expect(mocks.remove).not.toHaveBeenCalled()
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '取消' }))
    expect(mocks.remove).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: '批量删除' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '删除' }))

    await waitFor(() => expect(mocks.remove).toHaveBeenCalledTimes(2))
    expect(mocks.remove).toHaveBeenCalledWith('abc')
    expect(mocks.remove).toHaveBeenCalledWith('def')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('continues a partially failed batch, refreshes successes and retains only failed selections', async () => {
    const thirdImage = { ...image, id: 'ghi', filename: '第三张.png' }
    mocks.list.mockResolvedValue({
      ...libraryResponse,
      items: [image, otherImage, thirdImage],
      total: 3,
    })
    mocks.remove.mockImplementation(async (id: string) => {
      if (id === 'def') throw new Error('文件被占用')
    })
    renderPanel()
    await screen.findByRole('checkbox', { name: '选择 开心.gif' })
    fireEvent.click(screen.getByRole('checkbox', { name: '全选本页' }))
    fireEvent.click(screen.getByRole('button', { name: '批量删除' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '删除' }))

    await waitFor(() => expect(mocks.remove).toHaveBeenCalledTimes(3))
    await waitFor(() => expect(mocks.list.mock.calls.length).toBeGreaterThan(1))
    expect(screen.getByRole('checkbox', { name: '选择 开心.gif' })).not.toBeChecked()
    expect(screen.getByRole('checkbox', { name: '选择 第二张.png' })).toBeChecked()
    expect(screen.getByRole('checkbox', { name: '选择 第三张.png' })).not.toBeChecked()
    expect(mocks.toast).toHaveBeenCalledWith(
      expect.objectContaining({
        variant: 'destructive',
        description: expect.stringContaining('文件被占用'),
      })
    )
  })

  it('clears selections when paging or searching', async () => {
    mocks.list.mockResolvedValue({ ...libraryResponse, total: 100 })
    renderPanel()
    fireEvent.click(await screen.findByRole('checkbox', { name: '选择 开心.gif' }))
    fireEvent.click(screen.getByRole('button', { name: '下一页' }))
    await waitFor(() => expect(mocks.list).toHaveBeenLastCalledWith(2, '', 24))
    expect(await screen.findByRole('checkbox', { name: '选择 开心.gif' })).not.toBeChecked()
    fireEvent.click(screen.getByRole('checkbox', { name: '选择 开心.gif' }))
    fireEvent.change(screen.getByRole('textbox', { name: '搜索图库' }), {
      target: { value: '开心' },
    })
    await waitFor(() => expect(mocks.list).toHaveBeenLastCalledWith(1, '开心', 24))
    expect(await screen.findByRole('checkbox', { name: '选择 开心.gif' })).not.toBeChecked()
  })

  it('loads native thumbnails lazily using one resolved backend base and opens the original', async () => {
    mocks.list.mockResolvedValue({ ...libraryResponse, items: [image, otherImage], total: 2 })
    mocks.resolvePath.mockResolvedValue('https://backend.example')
    renderPanel()
    const thumbnail = await screen.findByRole('img', { name: '开心.gif' })
    expect(thumbnail).toHaveAttribute('src', 'https://backend.example/images/abc')
    expect(thumbnail).toHaveAttribute('loading', 'lazy')
    expect(thumbnail).toHaveAttribute('decoding', 'async')
    expect(mocks.resolvePath).toHaveBeenCalledExactlyOnceWith('')
    fireEvent.click(screen.getByRole('button', { name: '预览 开心.gif' }))
    expect(mocks.open).toHaveBeenCalledWith({
      src: '/images/abc?original=true',
      alt: '开心.gif',
      authenticated: true,
    })
  })
})
