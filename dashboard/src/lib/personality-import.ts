export interface PersonalityProfile {
  name: string
  personality: string
  behavior_style: string
  reply_style: string
  dialogue_examples: string[]
  group_chat_prompt: string
  private_chat_prompts: string
}

export const PERSONALITY_IMPORT_LIMIT = 65536
export const PERSONALITY_IMPORT_EVENT = 'maibot:personality-import'
const PENDING_KEY = 'maibot-personality-import-v1'

export const PERSONALITY_IMPORT_EXAMPLE = JSON.stringify({
  format: 'maibot.personality',
  version: 1,
  profile: {
    name: '温柔的麦麦',
    personality: '温柔、好奇，喜欢和朋友分享日常。',
    behavior_style: '自然参与聊天，认真倾听，不强行找话题。',
    reply_style: '简短自然，语气温和。',
    dialogue_examples: ['情境：朋友拿拖延开玩笑\n对方：你是不是又拖到最后一刻了？\n麦麦：被你发现了，我这就开工。', '黑话：咕咕，表示拖延或爽约；朋友互相调侃时使用。'],
    group_chat_prompt: '留意群友之间的互动，适时参与，不必逐条回复。',
    private_chat_prompts: '关注对方的想法，保持自然连贯的一对一交流。',
  },
}, null, 2)

function object(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

/** 外部文本只允许声明人设字段，不接受配置、脚本或远程资源。 */
export function parsePersonalityImport(text: string): PersonalityProfile {
  if (text.length > PERSONALITY_IMPORT_LIMIT) throw new Error('导入内容不能超过 65536 个字符')
  const source = text.trim().replace(/^```(?:json)?\s*\n([\s\S]*?)\n```$/i, '$1')
  let data: unknown
  try { data = JSON.parse(source) } catch { throw new Error('内容不是有效 JSON，请按示例格式粘贴') }
  if (!object(data) || data.format !== 'maibot.personality' || data.version !== 1) {
    throw new Error('仅支持 format 为 maibot.personality、version 为 1 的人设')
  }
  if (Object.keys(data).some((key) => !['format', 'version', 'profile'].includes(key))) {
    throw new Error('顶层只允许 format、version 和 profile 字段')
  }
  const profile = data.profile
  if (!object(profile)) throw new Error('profile 必须是人设对象')
  const fields = ['name', 'personality', 'behavior_style', 'reply_style', 'dialogue_examples', 'group_chat_prompt', 'private_chat_prompts']
  if (Object.keys(profile).some((key) => !fields.includes(key))) throw new Error('profile 中包含不支持的字段')
  for (const key of ['name', 'personality', 'behavior_style', 'reply_style']) {
    if (typeof profile[key] !== 'string') throw new Error(`${key} 必须是字符串`)
  }
  const name = (profile.name as string).trim()
  for (const key of ['group_chat_prompt', 'private_chat_prompts']) {
    if (typeof profile[key] !== 'string') throw new Error(`${key} 必须是字符串`)
  }
  if (!name) throw new Error('人设名称不能为空')
  const examples = profile.dialogue_examples === undefined ? [] : profile.dialogue_examples
  if (!Array.isArray(examples) || !examples.every((example) => typeof example === 'string')) {
    throw new Error('dialogue_examples 必须是字符串数组')
  }
  return {
    name,
    personality: profile.personality as string,
    behavior_style: profile.behavior_style as string,
    reply_style: profile.reply_style as string,
    dialogue_examples: examples,
    group_chat_prompt: profile.group_chat_prompt as string,
    private_chat_prompts: profile.private_chat_prompts as string,
  }
}

/** 在鉴权跳转前保留文本；多留一个字符，让超限内容在预览中明确报错。 */
export function rememberPersonalityImport(hash: string): boolean {
  const text = new URLSearchParams(hash.replace(/^#/, '')).get('personality-import')
  if (text === null) return false
  sessionStorage.setItem(PENDING_KEY, text.slice(0, PERSONALITY_IMPORT_LIMIT + 1))
  window.dispatchEvent(new Event(PERSONALITY_IMPORT_EVENT))
  return true
}

export function readPersonalityImport(): string | null {
  return sessionStorage.getItem(PENDING_KEY)
}

export function clearPersonalityImport(): void {
  sessionStorage.removeItem(PENDING_KEY)
}
