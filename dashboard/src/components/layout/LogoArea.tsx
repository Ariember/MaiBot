import { useId } from 'react'
import { motion, useReducedMotion } from 'motion/react'

import { cn } from '@/lib/utils'

interface LogoAreaProps {
  sidebarOpen: boolean
}

const SIDEBAR_SPECTRUM_TRANSITION = {
  duration: 0.22,
  ease: [0.22, 1, 0.36, 1] as const,
}

export function LogoArea({ sidebarOpen }: LogoAreaProps) {
  const spectrumLayoutId = useId()
  // Logo 行与顶栏同高：图标在前、字标在后，字标用大小写混排。
  const prefersReducedMotion = useReducedMotion()
  const spectrumTransition = prefersReducedMotion
    ? { duration: 0 }
    : SIDEBAR_SPECTRUM_TRANSITION

  return (
    <div
      data-dashboard-logo-area="true"
      className="relative flex h-[var(--layout-sidebar-logo-height)] items-center border-b px-[var(--layout-sidebar-logo-padding-x)]"
    >
      <div
        className="relative flex w-full items-center justify-center overflow-visible lg:w-[calc(var(--layout-sidebar-width)-var(--layout-sidebar-logo-padding-x)-var(--layout-sidebar-logo-padding-x))] lg:flex-none"
      >
        {/* 移动端始终显示完整 Logo，桌面端根据 sidebarOpen 切换 */}
        <div
          className={cn(
            'flex h-10 shrink-0 items-center justify-start gap-2 transition-opacity duration-[220ms] motion-reduce:transition-none',
            !sidebarOpen && 'lg:pointer-events-none lg:opacity-0'
          )}
        >
          <span
            data-dashboard-logo-title="true"
            className="whitespace-nowrap text-xl font-bold text-primary-gradient"
          >
            MaiBot
          </span>
          {sidebarOpen && (
            <motion.img
              layoutId={`sidebar-logo-spectrum-${spectrumLayoutId}`}
              src="/maimai.ico"
              alt=""
              aria-hidden="true"
              draggable={false}
              data-dashboard-logo-spectrum="true"
              className="order-first h-7 w-7 shrink-0 object-contain"
              transition={spectrumTransition}
            />
          )}
        </div>
      </div>
      {/* 折叠图标与导航 Tab 复用相同的左边距和宽度。 */}
      {!sidebarOpen && (
        <motion.img
          layoutId={`sidebar-logo-spectrum-${spectrumLayoutId}`}
          src="/maimai.ico"
          alt=""
          aria-hidden="true"
          draggable={false}
          data-dashboard-logo-spectrum="true"
          data-dashboard-logo-spectrum-block="true"
          className="pointer-events-none absolute top-[1.625rem] left-[var(--layout-sidebar-nav-padding-collapsed)] h-7 w-[var(--layout-sidebar-nav-item-collapsed-width)] object-contain max-lg:hidden"
          transition={spectrumTransition}
        />
      )}
    </div>
  )
}
