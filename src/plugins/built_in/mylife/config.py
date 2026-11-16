"""Mai_mylife WebUI 配置模型。



所有分组和字段都提供中文标签和中文说明，避免 WebUI 直接显示

``user_id``、``work_start`` 等内部字段名。

"""

from __future__ import annotations


from maibot_sdk import Field, PluginConfigBase
from pydantic import field_validator, model_validator, TypeAdapter
from typing import Any, ClassVar, Dict, List, Literal

import re


PLUGIN_VERSION = "1.3.0"

CONFIG_SCHEMA_VERSION = "1.24.0"

_TIME_RE = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


def _qq_id(value: Any, field_name: str) -> str:

    text = str(value or "").strip()

    if text and not re.fullmatch(r"[0-9]+", text):
        raise ValueError(f"{field_name} 必须填写纯数字 QQ 号")

    return text


def _ui(
    label: str,
    hint: str,
    order: int,
    *,
    placeholder: str | None = None,
    hidden: bool = False,
    disabled: bool = False,
    enum_labels: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    """构造 MaiBot WebUI 使用的字段元数据。"""

    result: Dict[str, Any] = {
        "label": label,
        "hint": hint,
        "order": order,
    }

    if placeholder is not None:
        result["placeholder"] = placeholder

    if hidden:
        result["hidden"] = True

    if disabled:
        result["disabled"] = True

    if enum_labels:
        # 同时提供两种常见枚举翻译扩展，兼容不同 WebUI 渲染版本。

        result["enum_labels"] = enum_labels

        result["x-enumNames"] = [enum_labels[key] for key in enum_labels]

    return result


def _time(value: Any, default: str) -> str:
    """把非法时间恢复为安全默认值。"""

    text = str(value or "").strip()

    return text if _TIME_RE.fullmatch(text) else default


def _work_time(value: Any) -> str:

    text = str(value).strip()

    if not _TIME_RE.fullmatch(text):
        raise ValueError("工作时间必须为 HH:MM（00:00～23:59）")

    return text


def _migrate_reply_policy(data: Any, enabled_key: str) -> Any:

    if not isinstance(data, dict):
        return data

    legacy = {
        "mode",
        "gate_mode",
        "gate_scope",
        "gate_segment_types",
        "wake_probability",
        "force_wake_terms",
        "night_start",
        "night_end",
        "nap_start",
        "nap_end",
    }

    if not legacy.intersection(data) or {"reply_probability", "work_start", "work_end"}.intersection(data):
        return data

    migrated = dict(data)

    if data.get(enabled_key, False):
        if data.get("gate_mode", "time_window") == "time_window":
            migrated["work_start"] = data.get("night_end", "08:00")

            migrated["work_end"] = data.get("night_start", "22:30")

    # 旧关闭仅表示不限制休息期，不应意外关闭新的回复策略。

    migrated[enabled_key] = True

    return migrated


class PluginSettings(PluginConfigBase):
    """插件开关、模型与管理员配置。"""

    __ui_label__: ClassVar[str] = "基础设置"

    __ui_order__: ClassVar[int] = 0


    # SDK 2.7+ 强制要求 plugin.config_version，用于配置补齐与迁移判定。

    config_version: str = Field(
        default=CONFIG_SCHEMA_VERSION,
        description="配置 Schema 版本，请勿手动修改。",
        json_schema_extra=_ui(
            "配置版本",
            "由插件维护，请勿手动修改。",
            99,
            hidden=True,
            disabled=True,
        ),
    )

    enabled: bool = Field(
        default=False,
        description="麦日常总开关。关闭后停止日程维护和主动私聊。",
        json_schema_extra=_ui(
            "启用麦日常",
            "关闭后保留数据库，但停止后台生活记录与主动行为。",
            0,
            hidden=True,
        ),
    )

    admin_user_ids: List[str] = Field(
        default_factory=list,
        description="允许在私聊使用菜单、状态和管理诊断指令的 QQ 号列表。",
        json_schema_extra=_ui(
            "管理员 QQ 列表",
            "管理员无需同时创建用户档案即可使用管理类指令；关系和重要日期等个人功能仍需启用用户档案。留空时，第一个有效私聊用户自动成为管理员。",
            1,
            placeholder="123456789",
        ),
    )

    @field_validator("config_version", mode="before")
    @classmethod
    def normalize_config_version(cls, value: Any) -> str:

        # 只校正框架必需的版本号，其他旧配置值仍由 SDK 默认补齐，不重写用户资料。

        del value

        return CONFIG_SCHEMA_VERSION

    @field_validator("admin_user_ids", mode="before")
    @classmethod
    def normalize_admin_ids(cls, value: Any) -> List[str]:

        values = value if isinstance(value, list) else []

        result = []

        for item in values:
            user_id = _qq_id(item, "管理员 QQ")

            if user_id and user_id not in result:
                result.append(user_id)

        return result


class UserProfile(PluginConfigBase):
    """单个私聊网友的关系和免打扰设置。"""

    __ui_label__: ClassVar[str] = "私聊用户资料"


    user_id: str = Field(
        default="",
        description="QQ 用户 ID。",
        json_schema_extra=_ui(
            "QQ 号",
            "填写允许进入麦日常系统的 QQ 号。",
            0,
            placeholder="123456789",
        ),
    )

    enabled: bool = Field(
        default=True,
        description="是否记录该用户的互动和关系状态。",
        json_schema_extra=_ui(
            "启用用户档案",
            "关闭后不记录该用户互动，也不会注入生活上下文。",
            1,
        ),
    )

    role: Literal["owner", "friend"] = Field(
        default="friend",
        description="该私聊用户在麦麦关系中的权限角色。",
        json_schema_extra=_ui(
            "关系角色",
            "最多只能有一个主人；朋友不会获得主人专属上下文和敏感能力。",
            3,
            enum_labels={"owner": "主人（owner）", "friend": "朋友（friend）"},
        ),
    )

    daily_proactive_max: int = Field(
        default=1,
        ge=0,
        le=20,
        description="未开启不限次数时，该用户每天最多实际收到的主动消息次数（硬上限，不是目标次数）。",
        json_schema_extra=_ui(
            "用户每日主动上限",
            "每日最多主动发送 N 次（硬上限，非目标次数）。实际次数常少于该值：受免打扰、冷却、候选评分和 Planner 自主决策约束。0 表示禁止主动消息；开启“每日主动不限次数”后忽略此值。主人通常填 2，朋友通常填 1。",
            4,
        ),
    )

    daily_proactive_unlimited: bool = Field(
        default=False,
        description="是否取消该用户的每日主动次数上限，由 Planner 自主判断是否发送。",
        json_schema_extra=_ui(
            "每日主动不限次数",
            "开启后忽略每日主动上限，由 Planner 结合生活契机和互动情况决定是否发送；仍遵守主动私聊开关、免打扰和冷却，不保证每天发送。",
            5,
        ),
    )

    initial_temperature: int = Field(
        default=30,
        ge=0,
        le=100,
        description="首次创建用户档案时使用的关系温度。",
        json_schema_extra=_ui(
            "初始关系温度",
            "仅首次创建档案时使用。30 表示“认识”，不会自动进入恋爱语气。",
            6,
        ),
    )

    quiet_start: str = Field(
        default="00:00",
        description="该用户免打扰时段开始时间。",
        json_schema_extra=_ui(
            "免打扰开始",
            "此时间后不向该用户主动发消息，支持跨午夜时段。格式 HH:MM。",
            7,
            placeholder="00:00",
        ),
    )

    quiet_end: str = Field(
        default="08:00",
        description="该用户免打扰时段结束时间。",
        json_schema_extra=_ui(
            "免打扰结束",
            "到达此时间后恢复主动消息。格式 HH:MM。",
            8,
            placeholder="08:00",
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_daily_limit(cls, value: Any) -> Any:
        """把 v1.6 的 -1 角色默认值迁移为明确数字。"""

        if not isinstance(value, dict):
            return value

        data = dict(value)

        try:
            configured = int(data.get("daily_proactive_max", 1))

        except (TypeError, ValueError):
            configured = 1

        if configured < 0:
            data["daily_proactive_max"] = 2 if str(data.get("role") or "friend") == "owner" else 1

        return data

    @field_validator("user_id", mode="before")
    @classmethod
    def normalize_user_id(cls, value: Any) -> str:

        return _qq_id(value, "私聊用户")

    @field_validator("quiet_start", mode="before")
    @classmethod
    def validate_quiet_start(cls, value: Any) -> str:

        return _time(value, "00:00")

    @field_validator("quiet_end", mode="before")
    @classmethod
    def validate_quiet_end(cls, value: Any) -> str:

        return _time(value, "08:00")


class UsersSettings(PluginConfigBase):
    """允许进入陪伴系统的私聊用户列表。"""

    __ui_label__: ClassVar[str] = "私聊用户"

    __ui_order__: ClassVar[int] = 1


    profiles: List[UserProfile] = Field(
        default_factory=list,
        description="允许进入麦日常系统的私聊用户。",
        json_schema_extra=_ui(
            "私聊用户列表",
            "麦麦的日程和生活记录全局共享，但每位用户的关系、额度和免打扰相互独立。",
            0,
        ),
    )

    owner_only_terms: List[str] = Field(
        default_factory=lambda: ["主人", "老公", "老婆", "亲爱的主人"],
        description="朋友回复中禁止出现的主人专属称呼。",
        json_schema_extra=_ui(
            "主人专属称呼",
            "朋友回复命中后会重生成一次，仍命中则静默。请只填写明确专属词。",
            1,
        ),
    )

    @model_validator(mode="after")
    def only_one_owner(self) -> "UsersSettings":

        user_ids = [profile.user_id for profile in self.profiles if profile.user_id]

        if len(user_ids) != len(set(user_ids)):
            raise ValueError("私聊用户 QQ 号不能重复")

        owners = [profile.user_id for profile in self.profiles if profile.enabled and profile.role == "owner"]

        if len(owners) > 1:
            raise ValueError("私聊用户中最多只能配置一个主人")

        return self


class EnvironmentSettings(PluginConfigBase):
    """现实天气刷新配置。"""

    __ui_label__: ClassVar[str] = "天气"

    __ui_order__: ClassVar[int] = 3


    weather_refresh_minutes: int = Field(
        default=30,
        ge=10,
        le=360,
        description="天气缓存刷新间隔。",
        json_schema_extra=_ui(
            "天气刷新间隔（分钟）",
            "后台刷新，不会在被动回复时等待网络请求。建议 30～60 分钟。",
            4,
        ),
    )


class MemorySettings(PluginConfigBase):
    """重要日期与提醒。"""

    __ui_label__: ClassVar[str] = "生活记忆"

    __ui_order__: ClassVar[int] = 5

    enabled: bool = Field(
        default=True,
        description="启用离线生活记忆结算。",
        json_schema_extra=_ui(
            "启用生活记忆",
            "总开关；关闭后保留已有日期数据。",
            0,
        ),
    )

    important_dates_enabled: bool = Field(
        default=True,
        description="识别并维护生日、考试、约定等日期。",
        json_schema_extra=_ui(
            "启用重要日期",
            "明确日期自动记录，模糊日期只进入待确认列表。",
            8,
        ),
    )

    date_model_analysis_enabled: bool = Field(
        default=False,
        description="本地规则未识别时调用快速模型分析日期。",
        json_schema_extra=_ui(
            "启用日期模型分析",
            "默认关闭；开启会增加私聊后的异步模型调用。",
            9,
        ),
    )

    date_candidate_retention_days: int = Field(
        default=90,
        ge=7,
        le=365,
        description="未确认日期候选的保留天数。",
        json_schema_extra=_ui(
            "日期候选保留天数",
            "过期候选只清理待确认项，不删除正式日期。",
            10,
        ),
    )

    date_reminder_lead_days: List[int] = Field(
        default_factory=lambda: [30, 7, 1, 0],
        description="重要日期提前准备和提醒的天数。",
        json_schema_extra=_ui(
            "重要日期提前天数",
            "默认提前 30、7、1 天以及当天生成一次专属契机。",
            11,
        ),
    )

    @field_validator("date_reminder_lead_days", mode="before")
    @classmethod
    def normalize_lead_days(cls, value: Any) -> List[int]:

        values = value if isinstance(value, list) else [30, 7, 1, 0]

        cleaned = []

        for item in values:
            try:
                number = int(item)

            except (TypeError, ValueError):
                continue

            if 0 <= number <= 365 and number not in cleaned:
                cleaned.append(number)

        return sorted(cleaned or [30, 7, 1, 0], reverse=True)


class NetworkSettings(PluginConfigBase):
    """联网总开关、宿主搜索、内置新闻源与见闻关联。"""

    __ui_label__: ClassVar[str] = "联网"

    __ui_order__: ClassVar[int] = 11

    enabled: bool = Field(
        default=False,
        description="联网总开关：联网工具、新闻阅读与主动探索的共同前提。",
        json_schema_extra=_ui(
            "启用联网",
            "关闭后联网工具、新闻与探索均跳过；内置新闻源可直接读取，搜索服务在主程序配置。",
            0,
        ),
    )

    tool_enabled: bool = Field(
        default=True,
        description="允许麦麦按需调用联网搜索工具。",
        json_schema_extra=_ui(
            "允许麦麦使用联网搜索工具",
            "总开关之上的工具子开关；工具只返回搜索摘要，不会直接发送消息。",
            1,
        ),
    )

    max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="单次搜索最多保留结果数。",
        json_schema_extra=_ui(
            "单次结果数",
            "联网工具、新闻和主动搜索共同使用；宿主服务可能有自己的上限。",
            2,
        ),
    )

    max_attempts: int = Field(
        default=3,
        ge=1,
        le=5,
        description="宿主搜索失败后的最大尝试次数。",
        json_schema_extra=_ui(
            "失败重试次数",
            "宿主搜索失败时按次数重试（短退避）；仍失败则记录历史并返回空结果。",
            3,
        ),
    )

    @field_validator("max_attempts", mode="before")
    @classmethod
    def clamp_legacy_attempts(cls, value: Any) -> Any:
        """旧降级链时代该字段上限 12（默认 12）；收紧到 1～5 后旧配置会整体校验失败，

        导致宿主暂停工具与调度。这里把超范围值夹回边界（12→5），旧 TOML 无需手改。"""

        try:
            return max(1, min(5, int(value)))

        except (TypeError, ValueError):
            return 3

    history_enabled: bool = Field(
        default=True,
        description="本地记录每次逻辑搜索的查询词与结果摘要。",
        json_schema_extra=_ui(
            "记录搜索历史",
            "记录联网工具、主动搜索和新闻阅读的查询词与结果摘要；查询词已做隐私清洗。",
            4,
        ),
    )

    history_retention_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="本地搜索历史保留天数。",
        json_schema_extra=_ui(
            "搜索历史保留天数",
            "到期自动清理；新闻与探索笔记仍按各自保留期管理。",
            5,
        ),
    )

    association_enabled: bool = Field(
        default=True,
        description="判断外界信息与麦麦自身的关系。",
        json_schema_extra=_ui(
            "启用自我关联",
            "先判断与人格、状态、兴趣或关系是否有关，再考虑分享。",
            6,
        ),
    )

    association_threshold: float = Field(
        default=0.65,
        ge=0,
        le=1,
        description="创建主动契机的最低关联分。",
        json_schema_extra=_ui(
            "关联分数阈值",
            "越高越克制；低于阈值只保留为近期见闻。",
            7,
        ),
    )

    proactive_share_enabled: bool = Field(
        default=True,
        description="允许高关联见闻创建主动契机。",
        json_schema_extra=_ui(
            "允许见闻主动分享",
            "仍受用户额度、休息、免打扰和 Planner 终审限制。",
            8,
        ),
    )

    context_item_limit: int = Field(
        default=3,
        ge=0,
        le=10,
        description="被动上下文最多包含的近期见闻数。",
        json_schema_extra=_ui(
            "近期见闻上下文数量",
            "设为 0 可只积累记录、不注入被动回复。",
            9,
        ),
    )

    news_enabled: bool = Field(
        default=False,
        description="启用低频新闻阅读。",
        json_schema_extra=_ui(
            "启用新闻阅读",
            "总开关之上的新闻子开关；优先内置订阅源，无结果时使用宿主搜索。",
            10,
        ),
    )

    news_sources: List[Literal["ithome", "solidot", "sspai"]] = Field(
        default_factory=lambda: ["ithome", "solidot", "sspai"],
        description="内置新闻订阅源；空列表表示仅使用宿主搜索。",
        json_schema_extra=_ui(
            "内置新闻源",
            "默认 IT之家、Solidot、少数派；读取公开 RSS，不向订阅源发送聊天内容。",
            10,
            enum_labels={"ithome": "IT之家", "solidot": "Solidot", "sspai": "少数派"},
        ),
    )

    news_daily_max: int = Field(
        default=1,
        ge=0,
        le=12,
        description="每天最多发起的新闻阅读次数。",
        json_schema_extra=_ui(
            "每日新闻阅读次数",
            "默认 1 次；失败或空结果也计入，避免持续请求。",
            11,
        ),
    )

    news_full_text_count: int = Field(
        default=3,
        ge=0,
        le=3,
        description="最多继续读取正文的结果数。",
        json_schema_extra=_ui(
            "正文读取数量",
            "经宿主 web.fetch 抓取正文，最多 3 篇；0 表示只用搜索摘要。",
            12,
        ),
    )

    news_max_concurrency: int = Field(
        default=2,
        ge=1,
        le=4,
        description="正文读取最大并发数。",
        json_schema_extra=_ui(
            "正文读取并发",
            "建议保持 1～2。",
            13,
        ),
    )

    news_max_article_chars: int = Field(
        default=8000,
        ge=1000,
        le=30000,
        description="保存和整理的正文最大字符数。",
        json_schema_extra=_ui(
            "正文长度上限",
            "超长正文会在本地截断。",
            14,
        ),
    )

    news_retention_days: int = Field(
        default=7,
        ge=1,
        le=90,
        description="新闻正文和摘要保留天数。",
        json_schema_extra=_ui(
            "新闻保留天数",
            "过期缓存自动清理。",
            15,
        ),
    )

    news_allowed_schedule_types: List[Literal["leisure", "rest"]] = Field(
        default_factory=lambda: ["leisure", "rest"],
        description="允许阅读新闻的日程类型。",
        json_schema_extra=_ui(
            "允许阅读的日程",
            "默认只在闲暇或休息时阅读。",
            16,
            enum_labels={"leisure": "闲暇", "rest": "休息"},
        ),
    )

    search_enabled: bool = Field(
        default=False,
        description="启用低频主动搜索。",
        json_schema_extra=_ui(
            "启用主动搜索",
            "总开关之上的主动探索子开关。",
            17,
        ),
    )

    search_daily_max: int = Field(
        default=1,
        ge=0,
        le=10,
        description="每天最多发起的主动搜索次数。",
        json_schema_extra=_ui(
            "每日主动搜索上限",
            "默认 1 次；失败或空结果也会计入，避免持续请求。",
            18,
        ),
    )

    search_include_chat_topics: bool = Field(
        default=False,
        description="允许使用匿名未完话题规划搜索。",
        json_schema_extra=_ui(
            "允许参考聊天话题",
            "默认关闭，避免把私聊内容变成外部搜索词。",
            19,
        ),
    )

    search_allowed_schedule_types: List[Literal["leisure", "rest", "travel"]] = Field(
        default_factory=lambda: ["leisure", "rest"],
        description="允许主动搜索的日程类型。",
        json_schema_extra=_ui(
            "允许搜索的日程类型",
            "只在空档、休息或按配置允许的出行段探索。",
            20,
            enum_labels={"leisure": "闲暇", "rest": "休息", "travel": "出行"},
        ),
    )

    search_note_retention_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="探索笔记保留天数。",
        json_schema_extra=_ui(
            "探索笔记保留天数",
            "过期笔记自动清理。",
            21,
        ),
    )


class ModelRoutingSettings(PluginConfigBase):
    """MaiBot 任务路由名，而不是 Provider API Key。"""

    __ui_label__: ClassVar[str] = "模型与成本编排"

    __ui_order__: ClassVar[int] = 13

    fast_task: str = Field(
        default="utils",
        description="快速整理任务名。",
        json_schema_extra=_ui(
            "快速任务",
            "默认 utils，用于日期分析、新闻整理等轻量任务。",
            0,
        ),
    )

    reasoning_task: str = Field(
        default="planner",
        description="推理任务名。",
        json_schema_extra=_ui(
            "推理任务",
            "默认 planner，用于搜索规划、自我关联等复杂判断；日常任务窗口无需模型。",
            1,
        ),
    )

    date_analysis_task: str = Field(
        default="",
        description="日期分析任务覆盖。",
        json_schema_extra=_ui(
            "日期分析任务覆盖",
            "留空继承快速任务。",
            10,
        ),
    )

    news_task: str = Field(
        default="",
        description="新闻整理任务覆盖。",
        json_schema_extra=_ui(
            "新闻整理任务覆盖",
            "留空继承快速任务。",
            11,
        ),
    )

    search_task: str = Field(
        default="",
        description="主动搜索任务覆盖。",
        json_schema_extra=_ui(
            "主动搜索任务覆盖",
            "留空继承推理任务。",
            12,
        ),
    )

    relevance_task: str = Field(
        default="",
        description="自我关联任务覆盖。",
        json_schema_extra=_ui(
            "自我关联任务覆盖",
            "留空继承推理任务。",
            13,
        ),
    )

    max_output_tokens: int = Field(
        default=0,
        ge=0,
        description="模型输出 token 上限；0=不限制，由服务商决定。",
        json_schema_extra=_ui(
            "输出 token 上限",
            "0=不限制（推荐）。推理模型的思考链占用输出预算，写死小上限会把正文挤成空响应；仅在对成本敏感时设正数。",
            22,
        ),
    )


class UsageSettings(PluginConfigBase):
    """插件模型调用统计。"""

    __ui_label__: ClassVar[str] = "Token 监控"

    __ui_order__: ClassVar[int] = 14

    enabled: bool = Field(
        default=True,
        description="记录插件与观察到的 Host 模型用量。",
        json_schema_extra=_ui(
            "启用 Token 统计",
            "不限制每日额度，只记录调用、Token、耗时与失败。",
            0,
        ),
    )

    retention_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="明细保留天数。",
        json_schema_extra=_ui(
            "明细保留天数",
            "每日聚合可长期保留，调用明细按此清理。",
            1,
        ),
    )


class ProactiveSettings(PluginConfigBase):
    """主动私聊的允许时段、统一间隔和契机评分；每日额度只在用户档案中配置。"""

    __ui_label__: ClassVar[str] = "主动私聊"

    __ui_order__: ClassVar[int] = 9


    enabled: bool = Field(
        default=True,
        description="是否启用主动私聊巡检。",
        json_schema_extra=_ui(
            "启用主动私聊",
            "关闭后麦麦仍维护日程和记忆，但不会主动找任何用户。",
            0,
        ),
    )

    patrol_interval_minutes: int = Field(
        default=180,
        ge=1,
        le=1440,
        description="同一用户的主动判断与实际发送共用的最小间隔，单位分钟。",
        json_schema_extra=_ui(
            "主动判断与发送间隔（分钟）",
            "默认 180，范围 1～1440。每位用户分别计时；Planner 沉默或实际发送后都至少等待此间隔。每轮最多判断一位到期用户，优先最久未判断者，多用户时可能略延后；没有生活契机时也可自主考虑。",
            1,
        ),
    )

    recent_user_silence_minutes: int = Field(
        default=30,
        ge=0,
        le=240,
        description="用户刚发言后暂停主动消息的时间。",
        json_schema_extra=_ui(
            "用户发言后冷却（分钟）",
            "用户刚刚聊过时无需再主动开场。默认等待 30 分钟。",
            3,
        ),
    )

    pending_expire_seconds: int = Field(
        default=120,
        ge=30,
        le=600,
        description="主动触发与 Replyer 回复关联的有效时间。",
        json_schema_extra=_ui(
            "主动回复确认窗口（秒）",
            "用于判断 Planner 是否真的生成了主动回复。通常无需修改。",
            4,
        ),
    )

    max_retries_per_opportunity: int = Field(
        default=2,
        ge=0,
        le=5,
        description="主动候选过期或 Planner 沉默后，同一生活契机最多重新进入候选池的次数。",
        json_schema_extra=_ui(
            "契机重试次数",
            "Planner 沉默或超时后，同一契机最多重试这么多次；超过后不再重复触发，避免反复打扰。0 表示不重试。",
            5,
        ),
    )

    score_threshold: float = Field(
        default=0.45,
        ge=0,
        le=2,
        description="生活契机作为 Planner 判断参考所需的最低综合分。",
        json_schema_extra=_ui(
            "主动候选分数阈值",
            "综合考虑契机、关系和用户活跃时间。未达标时不提供该契机，Planner 仍可自主判断是否联系，但不得虚构事件。",
            6,
        ),
    )

    work_start: str = Field(
        default="00:00",
        description="主动私聊允许开始的时间。",
        json_schema_extra=_ui(
            "主动开始时间",
            "HH:MM，按全局时区；支持跨午夜，与结束相同表示全天。普通私聊回复不受影响。",
            7,
        ),
    )

    work_end: str = Field(
        default="00:00",
        description="主动私聊允许结束的时间。",
        json_schema_extra=_ui(
            "主动结束时间",
            "到此时刻停止主动判断与发送；同时遵守用户免打扰时间。",
            8,
        ),
    )

    @field_validator("work_start", "work_end", mode="before")
    @classmethod
    def validate_work_time(cls, value: Any) -> str:

        return _work_time(value)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_intervals(cls, value: Any) -> Any:
        """旧判断和发送间隔合并时保留较长值，避免升级后增加打扰。"""

        if not isinstance(value, dict) or "min_interval_minutes" not in value:
            return value

        data = dict(value)

        intervals = [data.pop("min_interval_minutes")]

        if "patrol_interval_minutes" in data:
            intervals.append(data["patrol_interval_minutes"])

        intervals = [TypeAdapter(int).validate_python(interval) for interval in intervals]

        if any(not 1 <= interval <= 1440 for interval in intervals):
            raise ValueError("主动判断与发送间隔必须为 1～1440 分钟")

        data["patrol_interval_minutes"] = max(intervals)

        return data


class MaiLifeSettings(PluginConfigBase):
    """麦日常完整配置。"""

    plugin: PluginSettings = Field(
        default_factory=PluginSettings,
        json_schema_extra=_ui(
            "基础设置",
            "总开关、模型与管理员。",
            0,
        ),
    )

    users: UsersSettings = Field(
        default_factory=UsersSettings,
        json_schema_extra=_ui(
            "私聊用户",
            "配置允许互动和主动私聊的用户。",
            1,
        ),
    )

    environment: EnvironmentSettings = Field(
        default_factory=EnvironmentSettings,
        json_schema_extra=_ui(
            "天气",
            "天气刷新；时区和地区使用主程序全局配置。",
            3,
        ),
    )

    memory: MemorySettings = Field(
        default_factory=MemorySettings,
        json_schema_extra=_ui(
            "生活记忆", "重要日期和提醒。", 5,          ),
    )

    proactive: ProactiveSettings = Field(
        default_factory=ProactiveSettings,
        json_schema_extra=_ui(
            "主动私聊",
            "允许时段、公共冷却和评分；每日额度在每个私聊用户中设置。",
            9,
        ),
    )

    network: NetworkSettings = Field(
        default_factory=NetworkSettings,
        json_schema_extra=_ui(
            "联网",
            "总开关、搜索工具、搜索历史、见闻关联、新闻与主动探索。",
            11,
        ),
    )

    models: ModelRoutingSettings = Field(
        default_factory=ModelRoutingSettings,
        json_schema_extra=_ui(
            "模型与成本编排",
            "基础任务路由和高级覆盖。",
            13,
        ),
    )

    usage: UsageSettings = Field(
        default_factory=UsageSettings,
        json_schema_extra=_ui(
            "Token 监控",
            "调用次数、Token、耗时和失败统计。",
            14,
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_sections(cls, data: Any) -> Any:
        """将旧版私聊工作时段、用户边界和联网配置合并到对应设置。"""

        if not isinstance(data, dict):
            return data

        data = dict(data)

        context = data.pop("context", None)

        if isinstance(context, dict) and "owner_only_terms" in context:
            users = dict(data.get("users") or {})

            users.setdefault("owner_only_terms", context["owner_only_terms"])

            data["users"] = users

        rest = data.pop("rest_gate", None)

        if isinstance(rest, dict):
            rest = _migrate_reply_policy(rest, "enabled")

            if TypeAdapter(bool).validate_python(rest.get("enabled", True)):
                proactive = dict(data.get("proactive") or {})

                for key in ("work_start", "work_end"):
                    if key in rest:
                        proactive.setdefault(key, rest[key])

                data["proactive"] = proactive

        net = data.get("network") if isinstance(data.get("network"), dict) else {}

        info = data.pop("information", None)

        if isinstance(info, dict):
            for key, value in info.items():
                net.setdefault(key, value)

        api = data.pop("search_api", None)

        if isinstance(api, dict):
            for key in ("tool_enabled", "max_results", "max_attempts", "history_enabled", "history_retention_days"):
                if key in api:
                    net.setdefault(key, api[key])

        news = data.pop("news", None)

        if isinstance(news, dict):
            for old, new in (
                ("enabled", "news_enabled"),
                ("daily_max", "news_daily_max"),
                ("full_text_count", "news_full_text_count"),
                ("max_concurrency", "news_max_concurrency"),
                ("max_article_chars", "news_max_article_chars"),
                ("retention_days", "news_retention_days"),
                ("allowed_schedule_types", "news_allowed_schedule_types"),
            ):
                if old in news:
                    net.setdefault(new, news[old])

        search = data.pop("search", None)

        if isinstance(search, dict):
            for old, new in (
                ("enabled", "search_enabled"),
                ("daily_max", "search_daily_max"),
                ("include_chat_topics", "search_include_chat_topics"),
                ("allowed_schedule_types", "search_allowed_schedule_types"),
                ("note_retention_days", "search_note_retention_days"),
            ):
                if old in search:
                    net.setdefault(new, search[old])

        if net:
            data["network"] = net

        return data
