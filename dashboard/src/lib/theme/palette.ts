const clamp = (value: number, min: number, max: number): number => {
  if (value < min) return min
  if (value > max) return max
  return value
}

const roundToTenth = (value: number): number => Math.round(value * 10) / 10

const wrapHue = (value: number): number => ((value % 360) + 360) % 360

export const formatHSL = (h: number, s: number, l: number): string => {
  const safeH = roundToTenth(wrapHue(h))
  const safeS = roundToTenth(clamp(s, 0, 100))
  const safeL = roundToTenth(clamp(l, 0, 100))
  return `${safeH} ${safeS}% ${safeL}%`
}

export const hexToHSL = (hex: string): string => {
  let cleaned = hex.trim().replace('#', '')
  if (cleaned.length === 3) {
    cleaned = cleaned
      .split('')
      .map((char) => `${char}${char}`)
      .join('')
  }

  if (cleaned.length !== 6) {
    return formatHSL(0, 0, 0)
  }

  const r = Number.parseInt(cleaned.slice(0, 2), 16) / 255
  const g = Number.parseInt(cleaned.slice(2, 4), 16) / 255
  const b = Number.parseInt(cleaned.slice(4, 6), 16) / 255

  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  const delta = max - min
  const l = (max + min) / 2

  let h = 0
  let s = 0

  if (delta !== 0) {
    s = l > 0.5 ? delta / (2 - max - min) : delta / (max + min)
    switch (max) {
      case r:
        h = (g - b) / delta + (g < b ? 6 : 0)
        break
      case g:
        h = (b - r) / delta + 2
        break
      case b:
        h = (r - g) / delta + 4
        break
      default:
        break
    }
    h *= 60
  }

  return formatHSL(h, s * 100, l * 100)
}
