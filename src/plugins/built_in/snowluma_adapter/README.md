# 内置 OneBot 适配器（SnowLuma / NapCat）

本适配器随 MaiBot 发布，在本仓库维护，连接独立运行的 SnowLuma、NapCat 及其他 OneBot v11 客户端。

代码来自 [MaiBot-SnowLuma-Adapter](https://github.com/Mai-with-u/MaiBot-SnowLuma-Adapter)，作者 MaiBot Team，遵循 GPL-3.0-or-later 许可证。

```text
MaiBot（内置适配器） ↔ OneBot WebSocket ↔ SnowLuma / NapCat ↔ QQ
```

## OneBot v11 标准模式

插件 ID 为 `maibot-team.snowluma-adapter`，网关名为 `snowluma_gateway`。原 API、账号归属、聊天黑白名单和 QQ 官方适配器的身份同步接口保持兼容。

- `client.client_type = "auto"`（默认）：识别 SnowLuma / NapCat 时沿用对应专用逻辑，其他实现使用标准模式。
- `snowluma` / `napcat`：沿用原有文件、合并转发、语音和通知处理，不受标准模式的动作限制。
- `onebot_v11`：明确使用标准模式，字符串消息按 CQ 码解析；只允许标准动作及消息段，Host 的账号、群和消息 ID 转换为整数动作参数。文件上传、发送合并转发、厂商戳一戳、表情表态及 QZone 等扩展调用明确报错；扩展工具不向模型开放。

原 `adapter.snowluma.*` 和 `adapter.napcat.*` API 保留，并新增等价的 `adapter.onebot.*` 别名。前缀不切换客户端模式。

目前支持 `ws://主机:端口` 正向 WebSocket 根路径连接，不支持反向 WS、HTTP 或 OneBot v12。原有客户端配置无需修改；接入其他实现时可在插件配置页选择标准模式。

自动化测试包含原有功能回归、标准模式限制、CQ 码和本地模拟 WebSocket 收发；实际客户端的媒体可访问性与扩展能力仍以所用版本为准。

## 使用方法

1. 在 SnowLuma / NapCat 中创建正向 WebSocket 服务，记录主机、端口和连接令牌。

2. 打开 MaiBot WebUI 的适配器设置，找到「OneBot 适配器」，填写对应连接信息并启用。首次安装默认关闭。

3. 在「黑白名单规则」配置群聊和私聊权限；需要限制接收范围时，设置为默认不阅读，再添加允许的聊天。

Python 依赖随主程序安装，语音转码还需要系统 PATH 中可用的 `ffmpeg`。Docker 中连接运行在另一容器或宿主机上的客户端时，应填写容器可访问的地址。

## 从外置适配器升级

启动时会将 `plugins/` 中同 ID 外置适配器的 `config.toml`（包括连接信息和启用状态）接续到实例目录的 `data/plugins/maibot-team.snowluma-adapter/config.toml`，将旧 `plugins/data/napcat_adapter/ban_state.json` 接续到同一数据目录。目标文件已存在时保留目标内容。

接续成功后，旧插件目录保存在 `plugins/.builtin-backups/`，不再参与加载。已有多个同 ID 外置副本时继续报告重复冲突，需保留要使用的那一份后再启动。原独立源码仓库不受影响。

后续适配器代码、测试和发布均由 MaiBot 仓库管理；配置与禁言状态保存在实例数据目录，更新程序文件不会覆盖它们。

## 与 QQ 官方适配器同步成员身份

同时运行新版 QQ 官方适配器时，可在官方侧先绑定真实群号，并将「关联QQ号」填为本连接器登录的 QQ 号。之后官方适配器通过公开的 `identity_observations` API 获取指定账号、指定群的短期消息指纹和昵称、群名片；双向唯一的三条不同正文匹配成功后，自动建立本群用户身份对应关系，无需成员发送验证码。

本连接器不保存官方 OpenID 映射，也不缓存聊天正文。观察缓存最多 2000 条、每群 128 条，120 秒过期，断开连接时清空；私聊不采集。短文本和媒体消息不作为身份确认依据，但可为已确认的 QQ 号刷新名称。映射由官方适配器独立保存和管理，不用于管理员身份认证。

官方适配器还提供默认关闭的「SL 仅作身份查询」开关。启用后，由在线的官方适配器每 5 秒续期 `identity_only_lease`，本连接器才暂停对应账号的群消息、私聊和通知向 MaiBot 投递，同时通过标准网关状态撤销 Host 出站路由，避免同一条回复被两个适配器各发送一次；底层连接、群身份采集和查询继续运行。租约固定 15 秒有效，普通身份查询不会续期；停止续期后由独立到期任务恢复收发路由，不依赖新消息到达。断连、停用或重启清空，无任何持久化暂停开关，被暂停的消息不补投。

支持运行标记接口的 MaiBot 会在适配器列表中显示「仅身份查询」。本连接器通过通用能力 `runtime.set_status_badges` 上报标记和实际租约的到期时间，续期更新、释放或断连清除；主程序和浏览器按期限自动移除过期标记，不根据配置开关推断，也不需要按插件 ID 特判。旧主程序不支持该接口时会记录上报失败，租约控制仍独立生效。

身份查询模式中的指纹采集不受 SL 的发送者黑名单、正则黑白名单、机器人过滤或自身消息过滤限制，也不会经过 Host 的 SL 聊天名单校验；官方适配器仍只查询其已绑定的群。采集到的消息仅用于身份匹配，不投递给 MaiBot。租约结束后，新消息重新遵守 SL 原有过滤规则；即使租约在解析过程中到期，已绕过名单的那条消息也不会补投给 MaiBot。

## 群消息发送确认

连接 SnowLuma 时，群消息及合并转发在动作返回后还会查询对应消息，
只有消息 ID、目标群和正数群消息序号均匹配，才向 MaiBot 报告发送成功。
本地合成记录（序号为 0）、仅受理的异步动作或查询失败会报告失败；
“投递未确认”表示尚无真实群消息回执，消息仍可能迟到，适配器不会自动重发。

## 文本转 QQ 表情

在 WebUI 的适配器「插件设置」中开启「启用文本转QQ表情」（默认关闭），
或将 `[plugin]` 下的 `enable_text_face_conversion` 设为 `true`。
发送时，`[流泪]` 和 `/流泪` 均会转换为对应的 QQ 原生表情，支持连续或混合使用（如 `[流泪]/捂脸`）；
空格、标点、其他消息段和未知名称保持原样。名称必须完整匹配，
例如 `/捂脸不存在` 和 `[流泪不存在]` 不会被部分转换，只转换映射表中存在的表情名。
群聊、私聊及合并转发节点均生效，修改开关后对后续发送生效。

## 文本转 @

在「插件设置」开启「启用文本转@」（默认关闭），对应
`[plugin].enable_text_at_conversion = true`。群聊发送文本中的 `@QQ号`、
`@群名片`、`@昵称` 必须完整、唯一匹配当前群成员才转换为实际 @；
未知名称、重名、邮箱及查询失败时的文本保持原样，不自动转换 @全体成员。
真实 @ 的相邻去重始终生效，不受文本转换开关控制。
相邻的同目标 @（包括中间仅有空格或制表符）合并为一个，兼容宿主已有的实际 @；
不同目标、隔着正文或换行的 @ 保留。私聊与历史合并转发内容不处理。
修改开关后对后续发送生效。

## 其他插件调用 API

通过 SDK 的 `ctx.api.call` 调用，两种前缀均使用 `version="1"`：

```python
member = await self.ctx.api.call(
    "adapter.snowluma.group.get_group_member_info",
    version="1",
    group_id=123456,
    user_id=654321,
)
# 将上面的 adapter.snowluma. 替换为 adapter.napcat.，调用行为完全相同。

data = await self.ctx.api.call(
    "adapter.snowluma.action.call_data",
    version="1",
    action_name="get_group_info",
    params={"group_id": 123456},
)
```

`await self.ctx.api.list()` 可查看已注册的两组名称。前缀不会切换客户端类型；
实际能力仍取决于当前连接的客户端，两个前缀下的 QZone API 均仅支持 SnowLuma。

## 能力差异参考

| 维度 | napcat 画像 | snowluma 画像 |
| --- | --- | --- |
| 发送动作 | `send_group_msg` / `send_private_msg` | 通用 `send_msg` + `message_type` |
| 出站文件 | 内联 `file` 段 | 拆独立 `upload_group_file` / `upload_private_file` |
| 合并转发参数键 | `message` | `messages` |
| 语音 `get_record` 格式 | `wav` | `mp3`（silk 自动转码兜底） |
| QZone API | 不支持（显式报错） | 支持 |

token 鉴权不区分画像：连接时同时附带 `Authorization: Bearer` 头与 URL
`access_token` 参数（OneBot v11 两种标准方式），两类服务端各取所需。

## 配置页运行时控件

配置页新增 QQ 连接器状态及“重新连接”按钮。登录仍由 SnowLuma / NapCat 客户端完成：OneBot 接口没有统一扫码登录协议，因此此处不显示二维码。
