import type { ComponentType, ReactNode } from 'react'

export interface LayoutProps {
  children: ReactNode
}

export type WorkspaceMode = 'settings' | 'chat' | 'logs' | `plugin:${string}`

export type MenuIcon = ComponentType<{
  className?: string
  color?: string
  size?: number | string
}>

export interface MenuItem {
  icon: MenuIcon
  label: string
  path: string
  external?: boolean
  searchDescription?: string
  tourId?: string
  featureFlag?: 'agent' | 'computer' | 'files'
}

export interface MenuSection {
  title: string
  items: MenuItem[]
}
