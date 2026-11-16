import type { ReactNode } from 'react'

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SecurityTab } from '../SecurityTab'

const mocks = vi.hoisted(() => ({
  navigate: vi.fn(),
  toast: vi.fn(),
  validateToken: vi.fn((token: string) => ({
    isValid: token === 'ValidToken!123',
    rules: [
      {
        id: 'length',
        label: '长度规则',
        passed: token.length >= 8,
      },
      {
        id: 'strength',
        label: '强度规则',
        passed: token === 'ValidToken!123',
      },
    ],
  })),
}))



vi.mock('@tanstack/react-router', () => ({
  useNavigate: () => mocks.navigate,
}))

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: mocks.toast }),
}))

vi.mock('@/lib/token-validator', () => ({
  validateToken: mocks.validateToken,
}))

vi.mock('@/components/ui/dialog', () => ({
  Dialog: ({
    children,
    open,
    onOpenChange,
  }: {
    children: ReactNode
    open: boolean
    onOpenChange: (open: boolean) => void
  }) =>
    open ? (
      <div data-testid="token-dialog">
        <button type="button" onClick={() => onOpenChange(false)}>
          模拟关闭弹窗
        </button>
        {children}
      </div>
    ) : null,
  DialogContent: ({ children }: { children: ReactNode }) => <section>{children}</section>,
  DialogHeader: ({ children }: { children: ReactNode }) => <header>{children}</header>,
  DialogTitle: ({ children }: { children: ReactNode }) => <h2>{children}</h2>,
  DialogDescription: ({ children }: { children: ReactNode }) => <p>{children}</p>,
  DialogFooter: ({ children }: { children: ReactNode }) => <footer>{children}</footer>,
}))

vi.mock('@/components/ui/alert-dialog', () => ({
  AlertDialog: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  AlertDialogTrigger: ({ children }: { children: ReactNode }) => <>{children}</>,
  AlertDialogContent: ({ children }: { children: ReactNode }) => (
    <section data-testid="confirm-dialog">{children}</section>
  ),
  AlertDialogHeader: ({ children }: { children: ReactNode }) => <header>{children}</header>,
  AlertDialogTitle: ({ children }: { children: ReactNode }) => <h3>{children}</h3>,
  AlertDialogDescription: ({ children }: { children: ReactNode }) => <p>{children}</p>,
  AlertDialogFooter: ({ children }: { children: ReactNode }) => <footer>{children}</footer>,
  AlertDialogCancel: ({ children }: { children: ReactNode }) => (
    <button type="button">{children}</button>
  ),
  AlertDialogAction: ({ children, onClick }: { children: ReactNode; onClick?: () => void }) => (
    <button type="button" onClick={onClick}>
      {children}
    </button>
  ),
}))

describe('SecurityTab', () => {
  const clipboardWrite = vi.fn()
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: clipboardWrite },
    })
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
  })

  afterEach(() => {
    cleanup()
    mocks.navigate.mockReset()
    mocks.toast.mockReset()
    mocks.validateToken.mockClear()
    clipboardWrite.mockReset()
    fetchMock.mockReset()
    vi.useRealTimers()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('展示格式校验，并成功更新合法 Token 后跳转登录页', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ success: true }),
    })
    render(<SecurityTab />)

    fireEvent.click(screen.getAllByTitle('显示')[0])
    expect(screen.getByLabelText('新的访问令牌')).toHaveAttribute('type', 'text')

    const input = screen.getByLabelText('新的访问令牌')
    fireEvent.change(input, { target: { value: 'short' } })
    expect(screen.getByText('强度规则')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '更新自定义 Token' })).toBeDisabled()

    fireEvent.change(input, { target: { value: 'ValidToken!123' } })
    expect(screen.getByText('Token 格式正确，可以使用')).toBeInTheDocument()

    vi.useFakeTimers()
    fireEvent.click(screen.getByRole('button', { name: '更新自定义 Token' }))
    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(fetchMock).toHaveBeenCalledWith('/api/webui/auth/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ new_token: 'ValidToken!123' }),
    })
    expect(mocks.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: '更新成功' })
    )

    act(() => vi.advanceTimersByTime(1500))
    expect(mocks.navigate).toHaveBeenCalledWith({ to: '/auth' })
  })

  it('保留后端更新失败信息，并将网络异常归一为连接失败提示', async () => {
    render(<SecurityTab />)
    const input = screen.getByLabelText('新的访问令牌')
    fireEvent.change(input, { target: { value: 'ValidToken!123' } })

    fetchMock.mockResolvedValueOnce({
      ok: false,
      json: vi.fn().mockResolvedValue({ success: false, message: '后端拒绝更新' }),
    })
    fireEvent.click(screen.getByRole('button', { name: '更新自定义 Token' }))
    await waitFor(() =>
      expect(mocks.toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '更新失败',
          description: '后端拒绝更新',
          variant: 'destructive',
        })
      )
    )

    fetchMock.mockRejectedValueOnce(new Error('offline'))
    fireEvent.click(screen.getByRole('button', { name: '更新自定义 Token' }))
    await waitFor(() =>
      expect(mocks.toast).toHaveBeenCalledWith(
        expect.objectContaining({ description: '连接服务器失败' })
      )
    )
  })

  it('重新生成 Token 后支持复制，并在关闭弹窗后清理并跳转', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ success: true, token: 'generated-token' }),
    })
    clipboardWrite.mockResolvedValue(undefined)
    render(<SecurityTab />)

    fireEvent.click(screen.getByRole('button', { name: '确认生成' }))
    expect(await screen.findByText('generated-token')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledWith('/api/webui/auth/regenerate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    })

    fireEvent.click(screen.getByRole('button', { name: '复制 Token' }))
    await waitFor(() => expect(clipboardWrite).toHaveBeenCalledWith('generated-token'))
    expect(screen.getByRole('button', { name: '已复制' })).toBeInTheDocument()

    vi.useFakeTimers()
    fireEvent.click(screen.getByRole('button', { name: '我已保存，关闭' }))
    act(() => vi.advanceTimersByTime(500))

    expect(screen.queryByTestId('token-dialog')).not.toBeInTheDocument()
    expect(mocks.navigate).toHaveBeenCalledWith({ to: '/auth' })
  })

  it('复制失败和重新生成失败均给出破坏性提示', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: vi.fn().mockResolvedValue({ success: true, token: 'generated-token' }),
    })
    clipboardWrite.mockRejectedValue(new Error('clipboard denied'))
    render(<SecurityTab />)

    fireEvent.click(screen.getByRole('button', { name: '确认生成' }))
    await screen.findByText('generated-token')
    fireEvent.click(screen.getByRole('button', { name: '复制 Token' }))
    await waitFor(() =>
      expect(mocks.toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '复制失败',
          variant: 'destructive',
        })
      )
    )

    fetchMock.mockResolvedValueOnce({
      ok: false,
      json: vi.fn().mockResolvedValue({ success: false, message: '无法重新生成' }),
    })
    fireEvent.click(screen.getByRole('button', { name: '确认生成' }))
    await waitFor(() =>
      expect(mocks.toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '生成失败',
          description: '无法重新生成',
        })
      )
    )
  })

  it('仅生成弹窗展示 Token，复制成功后显示确认状态', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ success: true, token: 'generated-token' }),
    })
    clipboardWrite.mockResolvedValue(undefined)
    render(<SecurityTab />)

    expect(screen.queryByRole('button', { name: '复制 Token' })).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: '确认生成' }))
    await screen.findByText('generated-token')
    const currentCopyButton = screen.getByRole('button', { name: '复制 Token' })
    expect(currentCopyButton).toBeEnabled()

    vi.useFakeTimers()
    fireEvent.click(currentCopyButton)
    await act(async () => {
      await Promise.resolve()
    })

    expect(clipboardWrite).toHaveBeenCalledWith('generated-token')
    expect(mocks.toast).toHaveBeenCalledWith(
      expect.objectContaining({ title: '复制成功' })
    )
    expect(currentCopyButton.querySelector('.lucide-check')).not.toBeNull()

    expect(currentCopyButton).toHaveTextContent('已复制')
    expect(screen.queryByLabelText('您的访问令牌')).not.toBeInTheDocument()
  })

  it('复制生成的 Token 失败时给出破坏性提示', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ success: true, token: 'generated-token' }),
    })
    clipboardWrite.mockRejectedValue(new Error('denied'))
    render(<SecurityTab />)

    fireEvent.click(screen.getByRole('button', { name: '确认生成' }))
    await screen.findByText('generated-token')

    fireEvent.click(screen.getByRole('button', { name: '复制 Token' }))
    await waitFor(() =>
      expect(mocks.toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '复制失败',
          description: '请手动复制 Token',
          variant: 'destructive',
        })
      )
    )
  })

  it('通过 Dialog onOpenChange(false) 关闭生成弹窗后跳转登录页', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ success: true, token: 'generated-token' }),
    })
    render(<SecurityTab />)

    fireEvent.click(screen.getByRole('button', { name: '确认生成' }))
    await screen.findByText('generated-token')

    vi.useFakeTimers()
    fireEvent.click(screen.getByRole('button', { name: '模拟关闭弹窗' }))
    act(() => {
      vi.advanceTimersByTime(500)
    })

    expect(screen.queryByTestId('token-dialog')).not.toBeInTheDocument()
    expect(mocks.navigate).toHaveBeenCalledWith({ to: '/auth' })
  })

  it('重新生成接口抛错时提示连接失败', async () => {
    fetchMock.mockRejectedValue(new Error('offline'))
    render(<SecurityTab />)

    fireEvent.click(screen.getByRole('button', { name: '确认生成' }))
    await waitFor(() =>
      expect(mocks.toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '生成失败',
          description: '连接服务器失败',
          variant: 'destructive',
        })
      )
    )
  })

  it('重新生成失败且无 message 时回退默认文案', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      json: vi.fn().mockResolvedValue({ success: false }),
    })
    render(<SecurityTab />)

    fireEvent.click(screen.getByRole('button', { name: '确认生成' }))
    await waitFor(() =>
      expect(mocks.toast).toHaveBeenCalledWith(
        expect.objectContaining({
          title: '生成失败',
          description: '无法生成新 Token',
        })
      )
    )
  })

  it('仅空白的新 Token 通过校验时仍按输入错误拦截更新', async () => {
    mocks.validateToken.mockReturnValue({
      isValid: true,
      rules: [{ id: 'length', label: '长度规则', passed: true }],
    })
    render(<SecurityTab />)

    fireEvent.change(screen.getByLabelText('新的访问令牌'), {
      target: { value: '   ' },
    })
    expect(screen.getByRole('button', { name: '更新自定义 Token' })).toBeEnabled()

    fireEvent.click(screen.getByRole('button', { name: '更新自定义 Token' }))
    expect(fetchMock).not.toHaveBeenCalled()
    expect(mocks.toast).toHaveBeenCalledWith(
      expect.objectContaining({
        title: '输入错误',
        description: '请输入新的 Token',
        variant: 'destructive',
      })
    )
  })
})
