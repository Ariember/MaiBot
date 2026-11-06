import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { getComputerStatus, inputComputer } from '@/lib/computer-api'
import { ComputerDesktop } from '../agent/ComputerDesktop'

vi.mock('react-i18next', () => ({ useTranslation: () => ({ t: (key: string) => key }) }))
vi.mock('@/lib/computer-api', () => ({
  getComputerStatus: vi.fn(),
  getComputerFrame: async () => new Blob(['frame']),
  inputComputer: vi.fn(),
  controlComputer: vi.fn(),
  pollComputerOperation: vi.fn(),
}))

beforeEach(() => {
  vi.mocked(getComputerStatus).mockResolvedValue({
    enabled: true, paused: false, takeover: true, sandbox_running: true,
    pending_request: null, error: '',
  })
  vi.mocked(inputComputer).mockResolvedValue({ success: true, status: 'completed', operation_id: 'click' })
})

afterEach(cleanup)

async function desktop() {
  render(<ComputerDesktop />)
  const button = await screen.findByRole('button', { name: 'chat.computer.screen' })
  const image = screen.getByRole('img', { name: 'chat.computer.screen' })
  Object.defineProperties(image, { naturalWidth: { value: 800 }, naturalHeight: { value: 600 } })
  vi.spyOn(image, 'getBoundingClientRect').mockReturnValue(new DOMRect(10, 20, 400, 300))
  return button
}

it.each(['{Enter}', ' '])('用 %s 点击画面中心', async (key) => {
  const button = await desktop()
  button.focus()
  await userEvent.keyboard(key)
  await waitFor(() => expect(inputComputer).toHaveBeenCalledWith(
    [{ action: 'click', button: 'left', x: 400, y: 300 }], expect.any(AbortSignal),
  ))
})

it('鼠标点击保持缩放坐标', async () => {
  const button = await desktop()
  fireEvent.click(button, { detail: 1, clientX: 110, clientY: 95 })
  await waitFor(() => expect(inputComputer).toHaveBeenCalledWith(
    [{ action: 'click', button: 'left', x: 200, y: 150 }], expect.any(AbortSignal),
  ))
})

it('未接管时禁止输入', async () => {
  vi.mocked(getComputerStatus).mockResolvedValue({
    enabled: true, paused: false, takeover: false, sandbox_running: true,
    pending_request: null, error: '',
  })
  const button = await desktop()
  expect(button).toBeDisabled()
  fireEvent.click(button)
  expect(inputComputer).not.toHaveBeenCalled()
})

it('右键保持鼠标坐标，即使事件 detail 为零', async () => {
  const button = await desktop()
  fireEvent.contextMenu(button, { detail: 0, clientX: 110, clientY: 95 })
  await waitFor(() => expect(inputComputer).toHaveBeenCalledWith(
    [{ action: 'click', button: 'right', x: 200, y: 150 }], expect.any(AbortSignal),
  ))
})
