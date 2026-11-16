import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { APP_VERSION } from '@/lib/version'

import { AboutTab } from '../AboutTab'



// 更新卡片会请求后端，由自己的测试覆盖。
vi.mock('../SelfUpdateCard', () => ({ SelfUpdateCard: () => null }))

afterEach(() => cleanup())

const TECH_STACK_ITEMS = [
  'React 19.2.0',
  'TypeScript 5.7.2',
  'Vite 6.0.7',
  'TanStack Router 1.94.2',
  'shadcn/ui',
  'Radix UI',
  'Tailwind CSS 4.2.1',
  'Lucide Icons',
  'Python 3.12+',
  'FastAPI',
  'Uvicorn',
  'WebSocket',
  'Bun / npm',
  'ESLint 9.17.0',
]

const LIBRARY_ITEMS: Array<[name: string, license: string]> = [
  ['React', 'MIT'],
  ['shadcn/ui', 'MIT'],
  ['Radix UI', 'MIT'],
  ['Tailwind CSS', 'MIT'],
  ['Lucide React', 'ISC'],
  ['Iconify React', 'MIT'],
  ['Streamline Sharp', 'CC BY 4.0'],
  ['Streamline Block', 'CC BY 4.0'],
  ['TanStack Router', 'MIT'],
  ['Zustand', 'MIT'],
  ['React Hook Form', 'MIT'],
  ['Zod', 'MIT'],
  ['clsx', 'MIT'],
  ['tailwind-merge', 'MIT'],
  ['class-variance-authority', 'Apache-2.0'],
  ['date-fns', 'MIT'],
  ['Framer Motion', 'MIT'],
  ['vaul', 'MIT'],
  ['FastAPI', 'MIT'],
  ['Uvicorn', 'BSD-3-Clause'],
  ['Pydantic', 'MIT'],
  ['python-multipart', 'Apache-2.0'],
  ['TypeScript', 'Apache-2.0'],
  ['Vite', 'MIT'],
  ['ESLint', 'MIT'],
]

describe('AboutTab', () => {
  it('展示应用版本、维护者外链和分区标题', () => {
    render(<AboutTab />)

    expect(
      screen.getByRole('heading', { name: '关于 MaiBot Dashboard' }),
    ).toBeInTheDocument()
    expect(screen.getByText(`版本: ${APP_VERSION}`)).toBeInTheDocument()
    expect(screen.getByText('Ariember 维护的 MaiBot 个人分支 Web 管理界面。')).toBeInTheDocument()

    const githubLink = screen.getByRole('link', { name: /前往 GitHub/ })
    expect(githubLink).toHaveAttribute('href', 'https://github.com/Ariember/MaiBot')
    expect(githubLink).toHaveAttribute('target', '_blank')
    expect(githubLink).toHaveAttribute('rel', 'noopener noreferrer')

    const authorLink = screen.getByRole('link', { name: '@Ariember' })
    expect(authorLink).toHaveAttribute('href', 'https://github.com/Ariember')
    expect(authorLink).toHaveAttribute('target', '_blank')
    expect(authorLink).toHaveAttribute('rel', 'noopener noreferrer')

    expect(screen.getByRole('heading', { name: '开源项目' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '分支维护者' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '技术栈' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '开源致谢' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '开源许可' })).toBeInTheDocument()
    expect(screen.getByText('本项目采用 GNU General Public License v3.0 开源许可证。您可以自由地使用、修改和分发本软件，但必须保持相同的开源许可。')).toBeInTheDocument()
    expect(screen.getByText('本项目依赖的所有开源库均遵循各自的开源许可证（MIT、Apache-2.0、BSD 等）。感谢所有开源贡献者的无私奉献。')).toBeInTheDocument()
    expect(screen.getByText('MaiBot WebUI')).toBeInTheDocument()
  })

  it('列出全部技术栈与开源库许可证', () => {
    render(<AboutTab />)

    for (const item of TECH_STACK_ITEMS) {
      expect(screen.getAllByText(item).length).toBeGreaterThan(0)
    }

    expect(screen.getByText('前端框架')).toBeInTheDocument()
    expect(screen.getByText('UI 组件')).toBeInTheDocument()
    expect(screen.getByText('后端')).toBeInTheDocument()
    expect(screen.getByText('构建工具')).toBeInTheDocument()
    expect(screen.getByText('UI 框架与组件')).toBeInTheDocument()
    expect(screen.getByText('路由与状态管理')).toBeInTheDocument()
    expect(screen.getByText('表单处理')).toBeInTheDocument()
    expect(screen.getByText('工具库')).toBeInTheDocument()
    expect(screen.getByText('动画效果')).toBeInTheDocument()
    expect(screen.getByText('后端框架')).toBeInTheDocument()
    expect(screen.getByText('开发工具')).toBeInTheDocument()

    for (const [name, license] of LIBRARY_ITEMS) {
      const nameNode = screen.getByText(name, { selector: 'p.font-medium' })
      const row = nameNode.closest('div')?.parentElement
      expect(row, `找不到 ${name} 的许可证行`).not.toBeNull()
      expect(row).toHaveTextContent(license)
      expect(row?.querySelector('p.text-muted-foreground')).toHaveTextContent(/\S/)
    }

    expect(screen.getAllByText('CC BY 4.0')).toHaveLength(2)
    expect(screen.getByText('BSD-3-Clause')).toBeInTheDocument()
    expect(screen.getByText('ISC')).toBeInTheDocument()
  })
})
