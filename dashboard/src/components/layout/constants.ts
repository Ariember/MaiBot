import { createElement } from 'react'
import {
  Box,
  Database,
  FileText,
  HardDrive,
  Home,
  MessageCircle,
  MessageSquare,
  Monitor,
  Puzzle,
  Settings,
  Store,
  Sun,
  Wifi,
} from 'lucide-react'

import { createStreamlineIcon } from '@/components/ui/streamline-menu-icon'

import type { MenuIcon, MenuSection } from './types'

const HomeIcon = createStreamlineIcon('allergens-fish-remix', Home)
const LocalChatIcon = createStreamlineIcon('desktop-chat-remix', MessageCircle)
const BotConfigIcon = createStreamlineIcon('page-setting-remix', Settings)
const ModelIcon = createStreamlineIcon('module-remix', Box)
const PromptIcon = createStreamlineIcon('script-1-remix', FileText)
const LearningIcon = createStreamlineIcon('chat-bubble-square-write-remix', MessageSquare)
const KnowledgeIcon = createStreamlineIcon('user-sticker-square-remix', Database)
const PluginConfigIcon = createStreamlineIcon('application-add-remix', Puzzle)
const AdapterManagementIcon = createStreamlineIcon('router-wifi-network-solid', Wifi)
const PluginMarketIcon = createStreamlineIcon('store-2-solid', Store)
const DataTransferIcon: MenuIcon = (props) => createElement(HardDrive, props)

export const menuSections: MenuSection[] = [
  {
    title: "概览",
    items: [
      {
        icon: HomeIcon,
        label: "首页",
        path: '/',
        searchDescription: "查看仪表板概览",
      },
      { icon: LocalChatIcon, label: "麦麦聊天", path: '/chat' },
      { icon: Monitor, label: "电脑桌面与接管", path: '/computer', featureFlag: 'computer' },
    ],
  },
  {
    title: "配置管理",
    items: [
      {
        icon: BotConfigIcon,
        label: "麦麦设置",
        path: '/config/bot',
        searchDescription: "配置麦麦的详细设置和共享组",
      },
      {
        icon: ModelIcon,
        label: "模型管理",
        path: '/config/model',
        searchDescription: "配置模型参数",
        tourId: 'sidebar-model-management',
      },
      {
        icon: AdapterManagementIcon,
        label: "适配器设置",
        path: '/adapter-management',
      },
    ],
  },
  {
    title: "麦日常",
    items: [
      {
        icon: Sun,
        label: "日常配置",
        path: '/mylife',
        searchDescription: "配置麦麦的日常生活、日程、社交与主动消息",
      },
    ],
  },
  {
    title: "资源管理",
    items: [
      {
        icon: LearningIcon,
        label: "学习",
        path: '/resource/learning',
        searchDescription: "管理麦麦学习到的表达方式、黑话和表情包",
      },
      {
        icon: KnowledgeIcon,
        label: "长期记忆",
        path: '/resource/knowledge-base',
      },
    ],
  },
  {
    title: "扩展集成",
    items: [
      { icon: PluginConfigIcon, label: "插件扩展", path: '/plugin-config' },
      {
        icon: PluginMarketIcon,
        label: "插件市场",
        path: '/plugins',
        searchDescription: "浏览和安装插件",
      },
    ],
  },
  {
    title: "高级工具",
    items: [
      { icon: PromptIcon, label: "Prompt管理", path: '/config/prompts' },
      {
        icon: DataTransferIcon,
        label: "数据管理",
        path: '/data-transfer',
        searchDescription: "管理本地缓存，备份、导出或恢复 MaiBot 数据",
      },
    ],
  },
]
