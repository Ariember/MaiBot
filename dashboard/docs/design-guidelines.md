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
- 未来复古风格（`future-retro`）沿用自身的直角和小圆角规则。
