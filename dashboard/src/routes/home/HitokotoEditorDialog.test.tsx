import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { HitokotoEditorDialog } from './HitokotoEditorDialog'
import type { HitokotoSettings } from './hooks/useMaibotVersion'



function createDeferred<T>() {
  let resolve: (value: T | PromiseLike<T>) => void = () => {}
  let reject: (reason?: unknown) => void = () => {}
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise
    reject = rejectPromise
  })
  return { promise, resolve, reject }
}

const emptySettings: HitokotoSettings = {
  defaultEnabled: true,
  customItems: [],
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('HitokotoEditorDialog', () => {
  it('打开时展示标题、默认来源开关与空列表', () => {
    render(
      <HitokotoEditorDialog
        initialSettings={emptySettings}
        onOpenChange={vi.fn()}
        onSave={vi.fn()}
      />
    )

    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('编辑一言')).toBeInTheDocument()
    expect(screen.getByText('管理首页展示的一言来源与自定义内容。')).toBeInTheDocument()
    expect(screen.getByRole('switch', { name: '使用默认一言' })).toBeChecked()
    expect(
      screen.getByRole('button', { name: '还没有自定义内容，点击添加第一条' })
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '取消' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '保存' })).toBeInTheDocument()
  })

  it('取消关闭对话框且不保存', async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    const onSave = vi.fn()
    render(
      <HitokotoEditorDialog
        initialSettings={emptySettings}
        onOpenChange={onOpenChange}
        onSave={onSave}
      />
    )

    await user.click(screen.getByRole('button', { name: '取消' }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(onSave).not.toHaveBeenCalled()
  })

  it('保存当前设置后关闭', async () => {
    const user = userEvent.setup()
    const onOpenChange = vi.fn()
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(
      <HitokotoEditorDialog
        initialSettings={emptySettings}
        onOpenChange={onOpenChange}
        onSave={onSave}
      />
    )

    await user.click(screen.getByRole('button', { name: '保存' }))
    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith({
        defaultEnabled: true,
        customItems: [],
      })
    })
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('保存中禁用按钮，完成后恢复', async () => {
    const user = userEvent.setup()
    const deferred = createDeferred<void>()
    const onOpenChange = vi.fn()
    const onSave = vi.fn().mockReturnValue(deferred.promise)
    render(
      <HitokotoEditorDialog
        initialSettings={emptySettings}
        onOpenChange={onOpenChange}
        onSave={onSave}
      />
    )

    await user.click(screen.getByRole('button', { name: '保存' }))
    expect(screen.getByRole('button', { name: '保存中...' })).toBeDisabled()
    expect(screen.getByRole('button', { name: '取消' })).toBeDisabled()
    expect(onOpenChange).not.toHaveBeenCalled()

    await act(async () => {
      deferred.resolve()
      await deferred.promise
    })
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })

  it('可关闭默认来源、新增并编辑自定义内容后保存', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn().mockResolvedValue(undefined)
    const initialSettings: HitokotoSettings = {
      defaultEnabled: true,
      customItems: [{ id: 'keep', content: '原句', source: '原出处' }],
    }
    render(
      <HitokotoEditorDialog
        initialSettings={initialSettings}
        onOpenChange={vi.fn()}
        onSave={onSave}
      />
    )

    await user.click(screen.getByRole('switch', { name: '使用默认一言' }))
    expect(
      screen.getByRole('switch', { name: '使用默认一言' })
    ).not.toBeChecked()

    await user.clear(screen.getByRole('textbox', { name: '内容 1 正文' }))
    await user.type(
      screen.getByRole('textbox', { name: '内容 1 正文' }),
      '改写的一言'
    )
    await user.clear(screen.getByRole('textbox', { name: '内容 1 出处' }))
    await user.type(screen.getByRole('textbox', { name: '内容 1 出处' }), '新出处')
    await user.click(screen.getByRole('button', { name: '新增内容' }))
    await user.type(
      screen.getByRole('textbox', { name: '内容 2 正文' }),
      '第二条'
    )
    await user.type(
      screen.getByRole('textbox', { name: '内容 2 出处' }),
      '二号'
    )

    await user.click(screen.getByRole('button', { name: '保存' }))
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1))
    expect(onSave).toHaveBeenCalledWith({
      defaultEnabled: false,
      customItems: [
        { id: 'keep', content: '改写的一言', source: '新出处' },
        { id: expect.any(String), content: '第二条', source: '二号' },
      ],
    })
    expect(initialSettings.customItems[0]).toEqual({
      id: 'keep',
      content: '原句',
      source: '原出处',
    })
  })

  it('可从空态添加并删除自定义内容，关闭默认来源时展示留白提示', async () => {
    const user = userEvent.setup()
    const onSave = vi.fn().mockResolvedValue(undefined)
    render(
      <HitokotoEditorDialog
        initialSettings={emptySettings}
        onOpenChange={vi.fn()}
        onSave={onSave}
      />
    )

    await user.click(screen.getByRole('switch', { name: '使用默认一言' }))
    expect(screen.getByText('默认一言已停用且自定义列表为空，首页一言区域将保持留白。')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '还没有自定义内容，点击添加第一条' }))
    expect(screen.queryByText('默认一言已停用且自定义列表为空，首页一言区域将保持留白。')).not.toBeInTheDocument()
    expect(
      screen.getByRole('textbox', { name: '内容 1 正文' })
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '删除内容 1' }))
    expect(screen.getByText('默认一言已停用且自定义列表为空，首页一言区域将保持留白。')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '保存' }))
    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith({
        defaultEnabled: false,
        customItems: [],
      })
    })
  })
})
