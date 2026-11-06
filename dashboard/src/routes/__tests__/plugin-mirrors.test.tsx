import { cleanup, render, waitFor } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'

import { PluginMirrorsPage } from '../plugin-mirrors'

const navigate = vi.hoisted(() => vi.fn())
vi.mock('@tanstack/react-router', () => ({ useNavigate: () => navigate }))
afterEach(cleanup)

// 镜像设置已迁入市场页弹窗，旧路由只负责兼容跳转。
it.each([
  [false, '/plugins'],
  [true, '/plugins/embed'],
] as const)('旧镜像页 embedded=%s 跳转到 %s', async (embedded, to) => {
  const { container } = render(<PluginMirrorsPage embedded={embedded} />)
  await waitFor(() => expect(navigate).toHaveBeenCalledWith({ to, replace: true }))
  expect(container).toBeEmptyDOMElement()
})
