# WebUI 设计规范

## 公共组件与主题

- 页面优先复用 `src/components/ui/` 中的公共组件，由页面组织布局和业务交互。
- 颜色、字体、圆角和阴影使用主题令牌；公共外壳和数据面板复用 `styles/surfaces.css` 中的语义变量。
- 原版风格（`modern`）的视觉规则集中在 `styles/modern.css`，手机布局和样式集中在 `styles/mobile.css`。

## 圆角

原版风格采用接近苹果界面的柔和连续圆角，按控件和容器大小分层。亮色、暗色与桌面、手机共用同一套令牌。

### 尺寸层级

默认尺寸以 `1rem = 16px` 换算；页面使用工具类或 CSS 变量，不直接写固定像素圆角。

| 工具类 | CSS 变量 | 默认尺寸 | 用途 |
| --- | --- | --- | --- |
| `rounded-sm` | `--visual-radius-sm` | `0.375rem` / 6px | 复选框、紧凑列表项、小型控件 |
| `rounded-md` | `--visual-radius-md` | `0.625rem` / 10px | 按钮、输入框、选择器、菜单 |
| `rounded-lg` | `--visual-radius-lg` | `1rem` / 16px | 普通卡片、数据面板、聊天气泡 |
| `rounded-xl` | `--visual-radius-xl` | `1.5rem` / 24px | 弹窗、浮动侧面板、手机首页和插件市场卡片 |
| `rounded-t-2xl` | `--radius-2xl` | `1.75rem` / 28px | 手机底部弹层的顶部圆角 |
| `rounded-3xl` | `--radius-3xl` | `2rem` / 32px | 手机表达审核等大尺寸卡片 |

`--radius-2xl` 和 `--radius-3xl` 分别由 `--visual-radius-xl` 的 `7/6` 和 `4/3` 推导。
公共面板的 `--surface-radius` 与聊天气泡的 `--chat-bubble-radius` 取 `--visual-radius-lg`。

### 连续曲线

矩形控件和容器统一使用 `corner-shape: superellipse(1.5)`，由 `styles/modern.css` 中的 `@supports` 规则集中应用。
使用 `rounded-*` 的元素沿用该规则；只使用语义属性设置圆角的新容器，应在同一处补充选择器。

### 设置与维护

- 外观设置以 `radius-md` 为基准，小、中、大、超大圆角按 `0.6 : 1 : 1.6 : 2.4` 同步调整。
- 修改默认值时，同步更新 [主题令牌](../src/lib/theme/tokens.ts) 中的亮色、暗色默认值和 [全局样式](../src/index.css) 中的初始值。
- 新页面沿用公共组件的圆角；内嵌区域按层级选择较小尺寸，避免相邻元素各写一套圆角。
- 上传面板等第三方组件的自定义样式同样使用主题圆角变量。

### 兼容与形状例外

- 不支持 `corner-shape` 的浏览器使用相同尺寸的普通圆弧圆角。
- 圆形头像、状态点、开关和胶囊使用 `rounded-full` 或既有圆弧规则，保留圆形和胶囊轮廓。
- 贴边弹层、拼接控件按布局保留直角和单侧圆角；继承父级圆角的裁剪区域同步继承 `corner-shape`。

## 层次与色彩

原版风格（`modern`）采用冷调中性色（色相 228、低饱和）与三层海拔，规则集中在 `styles/modern.css` 的 `:root[data-dashboard-style='modern']` 作用域。

- 三层海拔：画布（`--background` 叠淡蓝/紫/青环境光）→ 表面（卡片与页面外框，发丝边 `--mdn-hairline` 加分层柔影 `--mdn-elev-1`）→ 浮层（玻璃 `--mdn-glass-*`）。
- 选中片、开关、按钮高光等小型浮起用 `--mdn-elev-chip`；可交互卡片悬停升到 `--mdn-elev-2`。
- 主操作按钮保持墨黑（暗色为浅色）配顶部内高光；焦点圈、开关、复选、单选、滑块与选中行统一使用 `chart-1` 蓝。
- 列表行选中通用钩子：元素标 `data-list-selected="true"`，材质由 `--list-selected-*` 变量决定；可复用 `data-dashboard-list-item` / `data-dashboard-selection-card` 的 `data-selected` 获得同一效果。
- 侧栏当前页为凸起小贴片；导航图标按组内位置轮换 `chart-1`~`chart-5`（`--nav-accent`）。
- 页内多彩沿用既有轮换：卡片、分区面板与资源行按位置取 `--colorful-accent`，首页指标按语义固定图表色。
