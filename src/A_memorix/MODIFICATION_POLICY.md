# A_Memorix 维护约定

`src/A_memorix` 是本仓库直接维护的长期记忆子系统，功能开发、修复、审查和发布随 MaiBot 一起进行。

## 维护范围

- 核心实现、存储、检索、运行时与离线脚本：`src/A_memorix/`
- 宿主调用与聊天记忆写回：`src/services/memory_service.py`、`src/services/memory_flow_service.py`
- WebUI 接口与页面：`src/webui/routers/memory.py`、`dashboard/src/lib/memory-api.ts`、`dashboard/src/routes/resource/knowledge-base/`、`dashboard/src/routes/resource/knowledge-graph/`
- 主配置定义：`src/config/` 中的 `a_memorix` 配置
- 提示词：`prompts/` 中的记忆模板，中文、英文和日文同步维护
- 回归测试：`pytests/A_memorix_test/` 及相关 WebUI、聊天工具测试

这些内容统一在本仓库修改。外部项目的改进按需评审引入，维护基线见[维护说明](../../docs/a_memorix_maintenance.md)。

## 修改要求

- 遵循现有分层，宿主接入、核心实现和 WebUI 各自承担对应职责。
- 保留既有接口、配置键和数据路径；需要改变契约时，同步修改调用方、文档与测试。
- 存储结构变更沿用已有 schema 升级机制，验证旧数据读取、写入和重启；向量模型或维度变更沿用已有重建流程。
- 业务模块通过 `chat_manager` 解析真实聊天流归属。
- 保留主循环调用与单写者约束，同步数据库和文件操作不得阻塞事件循环。
- 修改依赖以根 `pyproject.toml` 为准，同步根 `requirements.txt`。
- 按修改范围运行现有测试，避免无边界格式化或无关重构。
- 本地实验目录及依赖其运行的测试，未经明确确认不纳入共享历史。

## 来源与许可证

原始实现来自 [A-Dawn/A_memorix](https://github.com/A-Dawn/A_memorix)。保留原作者声明、`LICENSE` 和 `LICENSE-MAIBOT-GPL.md`，具体授权范围以许可证原文为准。
