

import { ComputerDesktop } from '@/components/agent/ComputerDesktop'
import { PageFrame } from '@/components/ui/surface'

export function ComputerPage() {
  return <PageFrame className="flex h-full min-h-0 flex-col">
    <header className="border-b p-4"><h1 className="font-semibold">{'电脑桌面与接管'}</h1></header>
    <ComputerDesktop />
  </PageFrame>
}
