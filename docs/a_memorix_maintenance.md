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

## 依赖与验证

依赖统一声明在根 `pyproject.toml`，同步根 `requirements.txt`。在仓库根目录准备开发环境并运行记忆测试：

```sh
uv sync --group dev --inexact
uv run --no-sync pytest -q pytests/A_memorix_test
```

修改 WebUI 接口或聊天工具时，同时运行对应的 `pytests/webui/`、`pytests/maisaka/` 测试；页面修改按项目 WebUI 验证规范执行。

## 许可证

保留 `src/A_memorix/LICENSE`、`src/A_memorix/LICENSE-MAIBOT-GPL.md` 与原作者声明。默认 AGPL-3.0 和面向 MaiBot 的额外 GPL 授权范围以这两个文件为准。
