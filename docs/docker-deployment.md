# Ariember/MaiBot 镜像部署与更新

本 fork 使用 GitHub Container Registry：

- 主程序：`ghcr.io/ariember/maibot:latest`
- 更新服务：`ghcr.io/ariember/maibot-updater:latest`
- 开发渠道将两者的标签换成 `dev`；发布同时保留完整提交 SHA 和版本标签。

镜像包含本仓库构建的 dashboard，不需要发布或安装自己的 `maibot-dashboard` 包。
Python 包自更新已移除；已有包安装仍可运行，请先备份实例目录，再迁移到容器部署。
源码部署的 WebUI 更新固定跟随 `Ariember/MaiBot`，不再检查上游或 CNB。

## 发布到 GitHub

工作流 `Publish GHCR Images` 在 main/dev 推送、`v*` 标签或手动运行时构建 AMD64、ARM64 镜像。
使用仓库自带的 `GITHUB_TOKEN` 和 `packages: write` 权限，无需 Docker Hub 或 PyPI 凭据。
手动运行时可选择 `latest` 或 `dev` 渠道。

首次发布后，在 GitHub 的两个 package 设置中将可见性设为 **Public**，以支持匿名拉取和 WebUI 检查。
仓库公开不代表新创建的 package 自动公开。镜像没有公开之前，更新检查会明确报错。
继承的 PyPI 发布工作流在本 fork 中已停用。

## 首次部署（Linux 或 WSL2 内的 Linux Docker 环境）

在部署目录放置本仓库的 `docker-compose.yml`，例如 `/opt/maibot`。
创建或合并 `.env`，保持目录为 **Docker 主机上的绝对路径**：

```dotenv
MAIBOT_DEPLOY_DIR=/opt/maibot
MAIBOT_IMAGE_CHANNEL=latest
```

更新服务内挂载的目录必须与主机同名，不能写容器内的别名。原生 Windows 路径不适用于此更新器；
在 WSL2 内部署时应从 Linux 目录运行 Compose。

```sh
docker compose pull core updater
docker compose up -d core updater napcat
```

WebUI 默认地址为 `http://主机地址:18001`。首次使用需按原部署流程完成配置和登录。
需要 SQLite 管理界面时再启动 `sqlite-web`；它不参与自动更新。

从已有源码/包实例迁移时，停止原程序后对应复制数据，不要同时运行两份实例：

| 原实例内容 | 当前 Compose 的主机目录 |
| --- | --- |
| `config/` | `docker-config/mmc/` |
| `data/` | `data/MaiMBot/` |
| `data/plugins/` 插件持久数据 | `data/MaiMBot-plugin-data/`（单独挂载，必须另外复制） |
| `plugins/` 插件源码 | `data/MaiMBot/plugins/` |
| `logs/` | `data/MaiMBot/logs/` |
| `depends-data/` | `depends-data/` |

保留原实例备份，确认聊天、记忆和插件加载正常后再清理。插件额外依赖会按声明重新安装，可能需要联网。

## WebUI 一键更新

在顶部更新按钮或「设置 → 关于」检查更新，选择 GitHub Container Registry，确认后更新。

执行器会重新验证确认的摘要、当前镜像和渠道，然后：

1. 先下载目标镜像，下载失败不停止当前服务。
2. 停止 `core`，将配置、数据、插件、日志和资源备份到 `docker-backups/<任务编号>/files/`。
3. 写入 `docker-compose.override.yml` 固定镜像摘要，重建 `core`，等待 WebUI 健康检查。
4. 将结果写入 `docker-update-state/last_result.json`，供页面读取。

`docker-compose.override.yml` 保留给更新器，不要加入其他配置；自定义部署参数写入主 Compose 文件或 `.env`。
更新器不会修改 NapCat、SQLite 管理服务或自身版本。更新执行器自身时，在没有更新任务运行的情况下执行：

```sh
docker compose pull updater
docker compose up -d --no-deps updater
```

更新中不要通过 SQLite 管理界面写入数据库。备份包含凭据和聊天数据，只应由部署管理员访问；
它们默认不自动删除，需按磁盘空间保留合适数量。健康检查验证 WebUI 可响应，不代表外部平台登录和所有插件均正常。

主程序容器不挂载 Docker socket。独立 updater 持有该权限，只消费本地文件队列，不提供网络控制端口；
它仍属于可信的宿主机管理组件，请勿使用未知来源的 updater 镜像。

## 失败与恢复

新程序启动前失败时尝试重新启动旧镜像。新程序启动后可能已经迁移数据库，若健康检查失败，
执行器会停止新容器并保留数据、备份及 `image-recovery.json`，不会直接把旧代码套在新数据库上。
执行器自身中断也会阻止后续更新，避免重复执行同一迁移。

先检查：

```sh
docker compose logs --tail=100 updater
docker compose logs --tail=100 core
```

从 `docker-update-state/last_result.json` 读取 `backup_path`，停止共享数据的服务，再显式恢复：

```sh
docker compose stop core updater napcat sqlite-web
docker compose run --rm --no-deps updater --restore /opt/maibot/docker-backups/实际任务编号
docker compose up -d updater napcat
```

恢复器验证备份路径与当前挂载一致，将失败后的数据保存到该备份目录下的 `after-failure-*`，
再恢复快照和旧镜像。旧镜像必须仍在本机，不要在恢复前 prune。恢复成功后清除任务阻止标记。
备份之后产生的数据不会自动合并，可从 `after-failure-*` 人工核对。

如果没有完整备份（如下载阶段或备份未完成就中断），先确认旧容器、数据和镜像仍完好，
停止 updater 后归档 `image-active.json`、`image-recovery.json` 和遗留请求，再重启 updater。
不要在未核对状态时直接删除标记或反复发起更新。
