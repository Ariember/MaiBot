import * as React from 'react'

import { cn } from '@/lib/utils'

interface AccentPanelProps extends React.HTMLAttributes<HTMLDivElement> {
  contentClassName?: string
}

const AccentPanel = React.forwardRef<HTMLDivElement, AccentPanelProps>(
  ({ className, contentClassName, children, ...props }, ref) => (
    <div
      ref={ref}
      data-dashboard-accent-panel="true"
      className={cn(
        'bg-card border-border text-card-foreground relative overflow-hidden border-2',
        className
      )}
      {...props}
    >
      <div
        data-dashboard-accent-panel-content="true"
        className={cn('relative min-h-full', contentClassName)}
      >
        {children}
      </div>
    </div>
  )
)
AccentPanel.displayName = 'AccentPanel'

export { AccentPanel }
