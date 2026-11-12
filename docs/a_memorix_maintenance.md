# 长期记忆系统维护

A_Memorix 由本仓库直接维护，源码、宿主接入、文档和测试随 MaiBot 一起发布。

## 来源与维护基线

- 原始仓库：[A-Dawn/A_memorix](https://github.com/A-Dawn/A_memorix)
- 上游对接分支 `MaiBot_branch`：`e54bf256dd984d174eaf5fc7b6a420db8b6a78a8`
- 已纳入的对接工作分支 `codex/memory-summary-identity`：`4dbf2f7059a470486a7eaf98fd525eafe092ed59`，包含上述对接分支历史
- 对应本仓库同步提交：`22e2dd7e0b8acd1b0d5a2b673f3fd57b3d7e0328`
- 自主维护基线：`c06e3f3b8`，包含后续宿主适配和记忆修复
- 自主维护起始日期：2026-11-12

开发与修复直接提交到本仓库。外部改动按具体功能评审引入，保留本地接口和数据兼容性。修改范围见 [A_Memorix 维护约定](../src/A_memorix/MODIFICATION_POLICY.md)。

## 代码与运行配置

- 核心实现与宿主：`src/A_memorix/`
- 业务调用与写回：`src/services/memory_service.py`、`src/services/memory_flow_service.py`
- WebUI 接口：`src/webui/routers/memory.py`
- 主程序配置：`config/bot_config.toml` 中的 `a_memorix` 配置节
- 运行数据：由 `a_memorix.storage.data_dir` 决定，默认 `data/a-memorix/`
- Web 上传暂存目录：`data/memory_upload_staging/`

离线脚本仍使用独立的 `config/a_memorix.toml`，其配置表名为 `storage`、`embedding` 等子系统相对名称，不带 `a_memorix.` 前缀；具体路径参数以各脚本的 `--help` 为准。执行写入或迁移脚本前，确认其数据目录指向目标实例，并停止占用同一目录的主程序。

维护归属调整沿用现有包路径、配置键、存储格式和 `.amembundle` 格式。涉及数据结构或向量模型的后续变更，使用已有迁移与重建机制，并验证历史数据。

## 聊天记忆的调用分工

- 普通聊天自动召回直接使用近期对话，优先保留最新消息，查询文本最多 1000 字符；沿用消息数触发、冷却和缓存，不额外调用生成模型概括查询。
- 人物事实抽取按真实会话、人物、用户消息 ID 和完整证据文本去重，最近 256 个成功窗口只处理一次。合法空结果也视为完成；提取或写入失败可重试，出现新消息或补充上下文则重新抽取。机器人回复“好的、收到”等简短确认也会处理用户证据。
- 人物画像作为简短背景注入；详细经历、时间范围和综合追忆通过 `query_memory` 按需查询。人物定向检索未命中后放宽人物限制时，仍保留原检索模式和时间范围。
- 聊天摘要增量写入，事件和人物画像通过现有后台队列派生。事实状态变更沿用有效期与历史记录，召回时区分当前状态和指定时间内的状态。
- 查询工具和回复参考共同保留来源与已知时间，分别标注事件时间、人物事实的消息观察时间、状态有效期和入库时间。

### 取舍与边界

人物事实抽取去重仅在当前服务生命周期内生效，重启或窗口淘汰后可能再次抽取；持久化写入仍由现有外部 ID 和事实账本去重。直接使用近期对话减少一次生成调用，也保留了原话中的噪声；召回质量仍需结合实际聊天评估。

### 同类产品参考

| 产品 | 借鉴机制 |
| --- | --- |
| [Mem0 OSS v3](https://docs.mem0.ai/migration/oss-v2-to-v3) | 单次抽取、ADD-only，减少写入模型调用；事实更新仍由本地账本处理。 |
| [Graphiti / Zep](https://github.com/getzep/graphiti/blob/main/graphiti_core/utils/maintenance/edge_operations.py) | 区分事实有效时间与系统记录时间，旧状态失效后保留历史。 |
| [Letta MemFS](https://docs.letta.com/concepts/memfs/index.md) | 短记忆常驻上下文，详细历史按需读取。 |
| [Hindsight](https://github.com/vectorize-io/hindsight/blob/main/hindsight-docs/blog/2026-07-24-recall-vs-reflect.md) | 召回与推理分层，普通聊天轻量召回，复杂问题再结合证据推理。 |
| [EverOS](https://github.com/EverMind-AI/EverOS/blob/main/docs/architecture.md) | 按对话边界保存事件，后台派生事实和画像。 |

## 依赖与验证

依赖统一声明在根 `pyproject.toml`，同步根 `requirements.txt`。在仓库根目录准备开发环境并运行记忆测试：

```sh
uv sync --group dev --inexact
uv run --no-sync pytest -q pytests/A_memorix_test
```

修改 WebUI 接口或聊天工具时，同时运行对应的 `pytests/webui/`、`pytests/maisaka/` 测试；页面修改按项目 WebUI 验证规范执行。

## 许可证

保留 `src/A_memorix/LICENSE`、`src/A_memorix/LICENSE-MAIBOT-GPL.md` 与原作者声明。默认 AGPL-3.0 和面向 MaiBot 的额外 GPL 授权范围以这两个文件为准。
