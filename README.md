# MaiBot

MaiBot（麦麦）是一个基于大语言模型的可交互智能体，可通过聊天平台或内置网页聊天室进行对话，并提供人设配置、记忆与表达学习、插件扩展和 Web 管理界面。

本仓库是 [MaiBot](https://github.com/Mai-with-u/MaiBot) 的个人 Fork。原项目及主要功能由上游团队与贡献者开发，感谢他们的开源工作。

[部署与更新](docs/docker-deployment.md) · [WebUI 说明](dashboard/README.md) · [更新日志](changelogs/changelog.md) · [上游文档](https://docs.mai-mai.org)

使用前请阅读 [用户协议](EULA.md) 与 [隐私协议](PRIVACY.md)。

## 功能概览

- **聊天与人设**：支持群聊、私聊和网页本地对话，可配置与切换人设。
- **记忆与学习**：管理聊天记忆、人物关系、表达方式和黑话学习。
- **WebUI 管理**：配置模型提供商、分配模型任务，查看实时日志、调用统计和资源。
- **麦日常**：内置日程、天气、关系与重要日期、阅读、联网见闻和主动私聊，可在侧边栏独立配置。
- **插件与适配器**：内置 [OneBot 适配器](src/plugins/built_in/snowluma_adapter/README.md)，连接 SnowLuma、NapCat 和 OneBot v11 客户端；通过插件市场和 SDK 扩展其他能力。
- **扩展能力**：按需启用聊天文件收发、外接 Agent，以及 Windows 内置桌宠；各功能的要求见下方文档。

## 部署与启动

运行前需准备可用的模型 API，并配置提供商、模型及任务分配。接入外部聊天平台时，还需配置对应的适配器和平台客户端；也可以先在网页聊天室中体验。

### Docker 部署（推荐）

本 Fork 使用 GHCR 镜像，已包含本仓库构建的 WebUI，支持 AMD64 和 ARM64。部署环境为 Linux，或 WSL2 内的 Linux Docker 环境。

请按 [Docker 部署与更新指南](docs/docker-deployment.md) 完成以下步骤：

1. 在部署目录放置本仓库的 [docker-compose.yml](docker-compose.yml)。
2. 在 `.env` 中设置 `MAIBOT_DEPLOY_DIR` 为 Docker 主机上的实际绝对路径，并选择 `latest` 或 `dev` 镜像渠道。
3. 拉取并启动 `core`、`updater`；需要 QQ 接入时同时启动和配置 `napcat`。
4. 打开 `http://主机地址:18001`，按启动日志中的临时 Token 登录 WebUI，并完成配置。

指南同时包含旧实例迁移、WebUI 一键更新、备份位置和失败恢复步骤。更新器要求挂载路径与主机一致，WSL2 部署请使用 Linux 目录。

### 源码部署

适合本地开发或需要自行修改代码的场景。准备 **Git、Python 3.12+、[uv](https://docs.astral.sh/uv/getting-started/installation/)**；构建本 Fork 的 WebUI 还需要 **Node.js 22 和 Bun**。

**1. 获取源码**

```sh
git clone https://github.com/Ariember/MaiBot.git
cd MaiBot
```

**2. 构建本仓库的 WebUI**

```sh
cd dashboard
bun install --frozen-lockfile
bun run build
cd ..
```

**3. 安装依赖并初始化配置**

```sh
uv sync --inexact
uv run --no-sync maibot init
```

初始化会生成缺失的 `config/bot_config.toml` 和 `config/model_config.toml`，保留已有配置。前者用于机器人与功能设置，后者用于模型提供商、API Key、模型及任务分配；可编辑文件，也可启动后在 WebUI 中配置。

**4. 从仓库根目录启动**

```sh
uv run --no-sync bot.py
```

启动后访问 [http://127.0.0.1:8001](http://127.0.0.1:8001)，使用日志中的临时 Token 登录，再按页面提示设置固定 Token。完成模型配置后即可使用网页聊天室。

WebUI 直接加载 `dashboard/dist/`，无需设置额外环境变量。源码更新后如前端有变化，需重新构建；依赖有变化时运行 `uv sync --inexact`，以保留插件额外安装的依赖。

### 前端开发

保持后端运行，在另一个终端执行：

```sh
cd dashboard
bun run dev
```

开发页面位于 [http://127.0.0.1:7999](http://127.0.0.1:7999)，API 默认代理到本机 `8001` 端口。开发模式无需每次构建，更多说明见 [dashboard/README.md](dashboard/README.md)。

## 配置与数据

以下路径均相对于源码部署的运行目录；Docker 的主机目录映射见部署指南。

| 路径 | 用途 |
| --- | --- |
| `config/` | 机器人、模型等配置，包含 API 凭据 |
| `data/` | 数据库、聊天记录、记忆、资源及插件持久数据 |
| `plugins/` | 已安装的插件源码 |
| `logs/` | 运行日志与诊断信息 |
| `depends-data/` | 运行时使用的资源文件 |

手动迁移或备份时，先停止原实例再复制配置与数据，不要让两份实例同时使用同一数据目录。Docker 一键更新会按部署指南自动备份。发布问题报告时，请隐去 API Key、WebUI Token 和私人聊天内容。

## 文档导航

| 文档 | 内容 |
| --- | --- |
| [部署与更新](docs/docker-deployment.md) | 容器部署、迁移、备份与恢复 |
| [WebUI](dashboard/README.md) | 管理界面功能与前端开发 |
| [长期记忆维护](docs/a_memorix_maintenance.md) | 记忆系统维护范围、配置入口与回归验证 |
| [文件服务](docs/file-service.md) | 聊天附件、文件管理及接入限制 |
| [表情包与图库](docs/image-gallery.md) | 图库导入、标签识别、聊天收图与发图 |
| [Agent 连接](docs/agent-connections.md) | DSH / ACP 本机与远程连接 |
| [内置桌宠](docs/desktop-pet.md) | Windows 桌宠、皮肤与插件接口 |
| [麦日常](docs/mylife.md) | 日常功能、可视化配置与数据保存 |
| [内部聊天](docs/internal-chat.md) | 网页聊天室与桌宠的共享身份 |
| [人设导入](docs/personality-import.md) | 人设 JSON 与导入链接 |
| [插件开发指南](https://github.com/Mai-with-u/maibot-plugin-sdk/blob/main/docs/guide.md) | 插件 SDK 与开发说明 |
| [更新日志](changelogs/changelog.md) | 功能变化与修复记录 |
| [上游文档](https://docs.mai-mai.org) | MaiBot 使用说明与配置参考 |

涉及本 Fork 的镜像、更新源与部署差异时，以本仓库文档为准。

## 反馈与贡献

本 Fork 的问题与建议请提交到 [Ariember/MaiBot Issues](https://github.com/Ariember/MaiBot/issues)，附上版本或提交号、部署方式、复现步骤及脱敏日志。提交改动前请阅读 [项目开发规范](AGENTS.md)，并验证相关功能。

## 许可证与致谢

本项目遵循 [GPL-3.0](LICENSE) 许可证。原项目为 [Mai-with-u/MaiBot](https://github.com/Mai-with-u/MaiBot)，感谢上游团队、贡献者及所使用的开源项目。本 Fork 的维护与改动不代表上游官方发布或承诺。
