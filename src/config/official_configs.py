from typing import Dict, List, Literal, Optional

import re

from .config_base import ConfigBase, Field

RULE_TYPE_OPTION_DESCRIPTIONS = {
    "group": "群聊聊天流，item_id 填群号或群聊 ID",
    "private": "私聊聊天流，item_id 填用户 ID",
}

OVERSIZED_IMAGE_HANDLE_METHOD_DESCRIPTIONS = {
    "compress": "压缩图片并继续处理",
    "discard": "丢弃超过最大大小的图片组件",
}

ATTENTION_DRIFT_LEVEL_OPTION_LABELS = {
    "subtle": "轻微漂移",
    "active": "活跃联想",
    "scattered": "明显发散",
    "wild": "强烈跳跃",
}

ATTENTION_DRIFT_LEVEL_OPTION_DESCRIPTIONS = {
    "subtle": "只在很自然的触发点上轻轻联想一句，整体仍跟随当前话题。",
    "active": "允许更主动地抓有趣支线，但回复仍应保持清楚、短促、可追溯。",
    "scattered": "会更明显地抓支线和突然联想，回复里可以出现可理解的拐弯。",
    "wild": "强实验档位；可以有更强的跳跃、插话和突然联想，但必须能从最近消息找到触发点。",
}

ATTENTION_DRIFT_ANCHOR_OPTION_LABELS = {
    "strict": "严格回钩",
    "balanced": "自然回钩",
    "loose": "宽松关联",
}

ATTENTION_DRIFT_ANCHOR_OPTION_DESCRIPTIONS = {
    "strict": "每次联想后都要快速拉回当前话题，适合技术群或严肃场景。",
    "balanced": "可以短暂支线联想，但通常要让回复和最近消息保持明显关系。",
    "loose": "允许更自由的相关联想，但仍必须能从最近消息找到触发点。",
}

ATTENTION_DRIFT_REACTION_OPTION_LABELS = {
    "reserved": "少量短反应",
    "natural": "自然短反应",
    "lively": "活泼短反应",
}

ATTENTION_DRIFT_REACTION_OPTION_DESCRIPTIONS = {
    "reserved": "短反应很少出现，只在特别好接的话题上使用。",
    "natural": "偶尔先用短句、吐槽或语气词接住话题，再继续回复。",
    "lively": "更容易先用短促反应开头，但不能把回复拆得太碎。",
}

"""
须知：
1. 本文件中记录了所有的配置项
2. 所有新增的class都需要继承自ConfigBase
3. 所有新增的class都应在official_configs.py中的Config类中添加字段
4. 对于新增的字段，若为可选项，则应在其后添加Field()并设置default_factory或default
5. 所有的配置项都应该按照如下方法添加字段说明：
class ExampleConfig(ConfigBase):
    example_field: str
    \"""This is an example field\"""
    - 注释前面增加_warp_标记可以实现配置文件中注释在配置项前面单独一行显示
"""


class BotConfig(ConfigBase):
    """机器人配置类"""

    __ui_label__ = "基础"
    __ui_order__ = 10

    platform: str = Field(
        default="",
        json_schema_extra={
            "label": '备用主平台',
            "x-widget": "input",
            "x-layout": "inline-right",
            "x-input-width": "12rem",
            "x-row": "bot-platform-account",
        },
    )
    """适配器没有上报身份时使用的备用主平台，例如 qq。"""

    qq_account: str = Field(
        default="",
        json_schema_extra={
            "label": '备用 QQ 账号',
            "x-widget": "input",
            "x-layout": "inline-right",
            "x-input-width": "12rem",
            "x-row": "bot-platform-account",
        },
    )
    """适配器没有上报 QQ 身份时使用的备用账号 ID。"""

    platforms: list[str] = Field(
        default_factory=lambda: [],
        json_schema_extra={
            "label": '其他备用平台',
            "x-widget": "custom",
        },
    )
    """其他平台的备用账号，格式为 platform:账号；适配器身份存在时不参与判断。"""

    nickname: str = Field(
        default="麦麦",
        json_schema_extra={
            "label": '机器人昵称',
            "x-widget": "input",
        },
    )
    """麦麦显示和自称时使用的名字。"""

    alias_names: list[str] = Field(
        default_factory=lambda: [],
        json_schema_extra={
            "label": '别名',
            "x-widget": "custom",
            "advanced": True,
        },
    )
    """别人可能用来称呼麦麦的名字，用于辅助识别提及。"""


class EnvironmentConfig(ConfigBase):
    """全局地区与时间配置。"""

    __ui_parent__ = "bot"
    __ui_label__ = "地区与时间"

    timezone: str = Field(
        default="Asia/Shanghai",
        min_length=1,
        json_schema_extra={
            "label": '时区',
            "x-widget": "input",
        },
    )
    """全局 IANA 时区，用于日程、免打扰时段和自然日统计；不跟随服务器本地时区。"""

    city: str = Field(
        default="Shanghai",
        json_schema_extra={
            "label": '城市 / 地区',
            "x-widget": "input",
        },
    )
    """麦麦所在的城市或地区，用于天气等位置相关服务。"""

    city_id: int = Field(default=0, ge=0, json_schema_extra={"advanced": True})
    """Open-Meteo 城市编号，由可视化选择保存以区分同名城市；0 表示按城市名查询。"""


class PersonalityProfile(ConfigBase):
    """可手动切换的人设快照。"""

    name: str = Field(min_length=1, pattern=r"\S")
    """人设名称。"""
    personality: str
    """人格和身份设定。"""
    behavior_style: str
    """行为风格。"""
    reply_style: str
    """表达风格。"""
    dialogue_examples: List[str] = Field(default_factory=list)
    """供 Planner 按需选择的场景与黑话表达，仅用于示范表达方式。"""
    group_chat_prompt: str
    """群聊提示词。"""
    private_chat_prompts: str
    """私聊提示词。"""


class PersonalityConfig(ConfigBase):
    """人格配置类"""

    __ui_parent__ = "bot"
    __ui_label__ = "人格"

    profiles: List[PersonalityProfile] = Field(default_factory=list, json_schema_extra={"x-widget": "custom"})
    """备选人设库，由 WebUI 保存与切换；运行时使用下方当前人设字段。"""

    selected_profile: str = Field(default="", json_schema_extra={"x-widget": "custom"})
    """当前编辑的人设名称，空字符串表示尚未存入人设库。"""

    def model_post_init(self, context: Optional[object] = None) -> None:
        """名称作为切换标识，不能重复。"""
        super().model_post_init(context)
        names = [profile.name for profile in self.profiles]
        if len(names) != len(set(names)):
            raise ValueError("备选人设名称不能重复")

    personality: str = Field(
        default="是女大学生，现在正在上网聊天。一般不包容且善良，但有时候有点一反常态，表现出锐利攻击性。善于用人类的角度思考问题，聊天比较日常。",
        json_schema_extra={
            "label": '人格设定',
            "x-widget": "textarea",
            "x-textarea-min-height": 40,
            "x-textarea-rows": 1,
            "x-description-display": "icon",
        },
    )
    """麦麦的人格和身份设定，建议简短描述她是谁、是什么性格。"""

    behavior_style: str = Field(
        default=(
            "是女大学生，现在正在上网聊天。一般不包容且善良，但有时候有点一反常态，表现出锐利攻击性。善于用人类的角度思考问题，聊天比较日常。不会没话题硬找话题，具有足够的自主性，会自行搜集信息理解内容。"
        ),
        json_schema_extra={
            "label": '行为风格',
            "x-widget": "textarea",
            "x-textarea-min-height": 40,
            "x-textarea-rows": 1,
            "x-description-display": "icon",
        },
    )
    """Planner 使用的行动准则，例如何时参与聊天、如何观察局面以及何时保持安静。"""

    reply_style: str = Field(
        default="你的风格平淡简短，可以参考贴吧的回复风格。不滥用比喻或者生硬句子。视情况省略主语或者进行倒装，风格较为随意。",
        json_schema_extra={
            "label": '表达风格',
            "x-widget": "textarea",
            "x-textarea-min-height": 40,
            "x-textarea-rows": 1,
            "x-description-display": "icon",
        },
    )
    """麦麦平时说话的风格，例如简短、温和、吐槽或正式。"""

    dialogue_examples: List[str] = Field(
        default_factory=list,
        json_schema_extra={
            "label": '场景与黑话表达',
            "x-widget": "custom",
        },
    )
    """每项填写适用场景、表达方式或黑话用法，也可附对话样例；Planner 每轮按需选择多项，未选中的不参与回复，内容不作为真实聊天经历。"""


class ImageCacheCleanupConfig(ConfigBase):
    """图片缓存自动清理配置。"""

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "x-widget": "switch",
            "label": '启用图片缓存自动清理',
        },
    )
    """开启后会自动删除长期不用的图片缓存。"""

    check_interval_hours: float = Field(
        default=6.0,
        ge=1.0 / 60.0,
        json_schema_extra={
            "x-widget": "input",
            "label": '清理检查间隔（小时）',
        },
    )
    """每隔多少小时检查一次旧图片。"""

    image_file_retention_days: int = Field(
        default=14,
        ge=1,
        json_schema_extra={
            "x-widget": "input",
            "label": '图片文件保留天数',
        },
    )
    """图片文件多久没被使用后可以删除。"""

    no_file_result_retention_days: int = Field(
        default=30,
        ge=1,
        json_schema_extra={
            "x-widget": "input",
            "label": '图片理解保留天数',
        },
    )
    """图片文件删掉后，识别文字还能保留多久。"""


class VisualConfig(ConfigBase):
    """视觉配置类"""

    __ui_label__ = "视觉"
    __ui_order__ = 60

    image_quality: Literal["normal", "high"] = Field(
        default="normal",
        json_schema_extra={
            "x-widget": "discrete-slider",
            "label": '图片画质',
            "x-option-labels": {"normal": "普通", "high": "超清"},
            "x-option-descriptions": {
                "normal": "最长边 512 像素，默认档位。",
                "high": "最长边 1024 像素，保留更多图片细节。",
            },
        },
    )
    """聊天普通图片发送给规划和回复模型时的画质：普通（normal）512、超清（high）1024 像素最长边。等比例缩小，小图不放大，不修改原图和表情包。"""

    max_image_num: int = Field(
        default=64,
        ge=0,
        json_schema_extra={
            "advanced": True,
            "x-widget": "input",
            "label": '多模态最大图片数',
        },
    )
    """一次多模态请求最多带多少张图，太大可能更慢更贵。"""

    wait_image_recognize_max_time: float = Field(
        default=32,
        ge=0,
        json_schema_extra={
            "x-widget": "input",
            "x-layout": "inline-right",
            "x-input-width": "7.5rem",
            "label": '识图最长等待时间',
        },
    )
    """等图片识别完成的最长秒数；0 表示不等待。"""

    handle_oversized_images: bool = Field(
        default=True,
        json_schema_extra={
            "x-widget": "switch",
            "x-layout": "inline-right",
            "x-row": "visual-image-compression",
            "label": '是否处理过大图片',
        },
    )
    """收到太大的图片时，是否自动压缩或丢弃。"""

    max_image_size_mb: float = Field(
        default=16.0,
        ge=0,
        json_schema_extra={
            "x-widget": "input",
            "x-layout": "inline-right",
            "x-input-width": "min(100%, 5.5rem)",
            "x-row": "visual-image-compression",
            "label": '最大图片大小(MB)',
        },
    )
    """超过这个大小的图片会按过大图片处理方法处理；0 表示不限。"""

    oversized_image_handle_method: Literal["compress", "discard"] = Field(
        default="compress",
        json_schema_extra={
            "x-widget": "select",
            "x-layout": "inline-right",
            "x-input-width": "min(100%, 8.5rem)",
            "x-row": "visual-image-compression",
            "x-option-descriptions": OVERSIZED_IMAGE_HANDLE_METHOD_DESCRIPTIONS,
            "label": '过大图片处理方法',
        },
    )
    """大图的处理方式：压缩后继续用，或直接丢弃。"""

    image_cache_cleanup: ImageCacheCleanupConfig = Field(default_factory=ImageCacheCleanupConfig)
    """定期清理旧图片缓存，减少磁盘占用。"""


class TalkRulesItem(ConfigBase):
    platform: str = Field(
        default="",
        json_schema_extra={
            "label": '平台',
        },
    )
    """规则作用的平台；留空表示不限定平台，* 表示任意平台。"""

    item_id: str = Field(
        default="",
        json_schema_extra={
            "label": '聊天流 ID',
        },
    )
    """规则作用的群号或用户 ID；留空表示不限定聊天，* 表示任意聊天。"""

    rule_type: Literal["group", "private"] = Field(
        default="group",
        json_schema_extra={
            "label": '聊天类型',
            "x-widget": "select",
            "x-option-descriptions": RULE_TYPE_OPTION_DESCRIPTIONS,
        },
    )
    """规则作用于群聊还是私聊。"""

    time: str = Field(
        default="",
        json_schema_extra={
            "label": '时间段',
            "x-widget": "talk-time",
        },
    )
    """规则生效时间；留空为兜底，* 为全天，也可填 23:00-02:00。"""

    value: float = Field(
        default=0.5,
        json_schema_extra={
            "label": '发言频率',
        },
    )
    """该规则下的发言频率；0 更安静，1 按正常频率。"""


class PrivateReplyPauseRule(ConfigBase):
    platform: str = Field(
        default="",
        min_length=1,
        json_schema_extra={"label": '平台'},
    )
    """私聊所在的平台，需填写具体平台。"""

    item_id: str = Field(
        default="",
        min_length=1,
        json_schema_extra={"label": '用户 ID'},
    )
    """私聊对象的用户 ID，需填写具体用户。"""

    paused: bool = Field(
        default=True,
        json_schema_extra={
            "label": '暂停回复',
            "x-widget": "switch",
        },
    )
    """开启后暂停这个私聊的回复；关闭则允许回复，覆盖全局私聊暂停设置。"""


class ChatReplyTimingConfig(ConfigBase):
    """聊天回复时机与频率配置类"""

    __ui_label__ = "回复频率"
    __ui_icon__ = "activity"

    message_debounce_seconds: float = Field(
        default=2.0,
        ge=0,
        le=8,
        json_schema_extra={
            "label": '群聊消息防抖（秒）',
            "x-widget": "slider",
            "step": 0.1,
        },
    )
    """群聊新消息到达后等待的秒数，0 表示关闭；默认 2 秒，可按 0.1 秒调整。
    后续消息从到达时重算等待；批次内纯表情包不延长等待。整批最多 8 秒，@或提及后最多 1 秒。
    调整时长从下一条有效消息起生效，不延长已到期批次；设为 0 会结束当前防抖等待。时间不包含模型生成和发送耗时。
    """

    private_message_debounce_seconds: float = Field(
        default=2.0,
        ge=0,
        le=8,
        json_schema_extra={
            "label": '私聊消息防抖（秒）',
            "x-widget": "slider",
            "step": 0.1,
        },
    )
    """私聊新消息到达后等待的秒数，与群聊独立，0 表示关闭；默认 2 秒，可按 0.1 秒调整。
    后续消息从到达时重算等待；批次内纯表情包不延长等待。整批最多 8 秒，@或提及后最多 1 秒。
    调整时长从下一条有效消息起生效，不延长已到期批次；设为 0 会结束当前防抖等待。时间不包含模型生成和发送耗时。
    """

    planner_message_steering: bool = Field(
        default=False,
        json_schema_extra={
            "label": '快速反应模式',
            "x-widget": "switch",
        },
    )
    """强制 Planner 使用流式请求；思考或输出期间收到新消息立即打断并带上新消息重新请求，wait 等待也可被新消息提前结束。"""

    talk_value: float = Field(
        default=1,
        ge=0,
        le=1,
        json_schema_extra={
            "label": '群聊频率',
            "x-widget": "slider",
            "x-row": "talk-values",
            "step": 0.001,
        },
    )
    """群聊里麦麦主动说话的频率；越小越安静。"""

    private_reply_paused: bool = Field(
        default=False,
        json_schema_extra={
            "label": '暂停私聊回复',
            "x-widget": "switch",
            "x-row": "talk-values",
        },
    )
    """开启后私聊只接收消息并维护历史，不进入思考；单个私聊可通过暂停规则覆盖此设置。"""

    private_reply_pause_rules: List[PrivateReplyPauseRule] = Field(
        default_factory=list,
        json_schema_extra={
            "label": '单个私聊暂停规则',
            "x-widget": "custom",
        },
    )
    """按具体平台和用户 ID 覆盖全局暂停设置，可在聊天流设置中切换或恢复跟随全局。"""

    mentioned_bot_reply: bool = Field(
        default=True,
        json_schema_extra={
            "label": '提及必回复',
            "x-widget": "switch",
            "x-row": "reply-switches",
        },
    )
    """开启后，只要消息提到麦麦名字就更容易回复。"""

    inevitable_at_reply: bool = Field(
        default=True,
        json_schema_extra={
            "label": 'At 必回复',
            "x-widget": "switch",
            "x-row": "reply-switches",
        },
    )
    """开启后，被 @ 时会尽量回复。"""

    no_action_backoff_base_seconds: float = Field(
        default=15,
        ge=0,
        json_schema_extra={
            "label": '空闲退避基准',
            "x-widget": "input",
            "x-layout": "inline-right",
            "x-input-width": "7.5rem",
            "x-description-display": "icon",
            "advanced": False,
        },
    )
    """连续决定不回复后，下一次检查前先等多久。"""

    no_action_backoff_cap_seconds: float = Field(
        default=300,
        ge=0,
        json_schema_extra={
            "label": '空闲退避上限',
            "x-widget": "input",
            "x-description-display": "icon",
            "advanced": True,
        },
    )
    """不回复退避等待的最长时间。"""

    no_action_backoff_start_count: int = Field(
        default=2,
        ge=1,
        json_schema_extra={
            "label": '空闲退避起点',
            "x-widget": "input",
            "x-description-display": "icon",
            "advanced": True,
        },
    )
    """连续几次不回复后开始放慢检查。"""

    no_action_backoff_bypass_pending_count: int = Field(
        default=6,
        ge=0,
        json_schema_extra={
            "label": '空闲退避绕过消息数',
            "x-widget": "input",
            "x-description-display": "icon",
            "advanced": True,
        },
    )
    """等待期间新消息达到多少条就立刻重新处理；0 表示不按条数打断等待。"""

    enable_talk_value_rules: bool = Field(
        default=False,
        json_schema_extra={
            "label": '启用动态发言频率规则',
            "x-widget": "switch",
        },
    )
    """开启后，可以按群聊或时间段单独调整发言频率；私聊不使用频率规则。"""

    talk_value_rules: list[TalkRulesItem] = Field(
        default_factory=lambda: [
            TalkRulesItem(platform="", item_id="", rule_type="group", time="00:00-08:59", value=0.8),
            TalkRulesItem(platform="", item_id="", rule_type="group", time="09:00-18:59", value=1.0),
        ],
        json_schema_extra={
            "label": '动态发言频率规则',
            "x-widget": "custom",
        },
    )
    """
    _wrap_动态发言频率规则；可让麦麦在某些群或时段更活跃或更安静。旧的私聊频率规则不再生效。
    """


class ChatReplyStyleConfig(ConfigBase):
    """聊天回复方式配置类"""

    __ui_label__ = "如何发言"
    __ui_icon__ = "message-square"

    group_quote_frequency: Literal["never", "occasionally", "often"] = Field(
        default="occasionally",
        json_schema_extra={
            "label": '群聊引用频率',
            "x-widget": "discrete-slider",
            "x-option-labels": {"never": "不引用", "occasionally": "偶尔引用", "often": "经常引用"},
        },
    )
    """全局群聊引用频率：不引用、偶尔引用、经常引用。按固定规律随机决定，经常引用的概率为偶尔引用的两倍；不影响私聊。"""

    private_quote_frequency: Literal["never", "occasionally", "often"] = Field(
        default="occasionally",
        json_schema_extra={
            "label": '私聊引用频率',
            "x-widget": "discrete-slider",
            "x-option-labels": {"never": "不引用", "occasionally": "偶尔引用", "often": "经常引用"},
        },
    )
    """全局私聊引用频率：不引用、偶尔引用、经常引用。结合用户连发条数、发言间隔和回复目标位置随机决定；经常引用的概率为偶尔引用的两倍。"""

    group_chat_prompt: str = Field(
        default=(
            "下面是聊天中的的内容，聊天中包含文字，图片和表情包等消息。\n"
            "回复尽量简短一些。最好一次对一个话题进行回复，但必须考虑不同群友发言之间的交互，免得啰嗦或者回复内容太乱。\n"
            "根据聊天内容自由发挥，但是要日常不浮夸，不要刻意找话题。\n"
            "不用刻意回复其他人发送的表情包。你可以适当发送表情包表达情绪。如果有人不喜欢你或者不理你，就不要强行回复，回复前读空气。不要每个人的消息都回复，适当回复其他话题。可以适当回过头回复之前用户的消息。\n"
        ),
        json_schema_extra={
            "label": '群聊提示词',
            "x-widget": "textarea",
        },
    )
    """_wrap_群聊通用提示词，告诉麦麦群聊中该怎么说话。"""

    private_chat_prompts: str = Field(
        default=(
            "你正在聊天，下面是正在聊的内容，其中包含聊天记录和聊天中的图片。\n"
            "回复尽量简短一些。请注意把握聊天内容。\n"
            "请考虑对方的发言频率，想法，思考自己何时回复以及回复内容。\n"
        ),
        json_schema_extra={
            "label": '私聊提示词',
            "x-widget": "textarea",
        },
    )
    """_wrap_私聊通用提示词，告诉麦麦私聊中该怎么说话。"""

    chat_prompts: list["ExtraPromptItem"] = Field(
        default_factory=lambda: [],
        json_schema_extra={
            "label": '额外 Prompt',
            "x-widget": "custom",
        },
    )
    """给指定群聊或私聊额外补充聊天要求；有特殊群规或语气要求时再加。"""


class ChatConfig(ConfigBase):
    """聊天配置类"""

    __ui_label__ = "聊天"
    __ui_order__ = 20
    __ui_use_subtabs__ = True
    __ui_root_sub_label__ = "聊天设置"

    enable_reply_at: bool = Field(
        default=True,
        json_schema_extra={
            "label": '允许回复时 @ 用户',
            "x-widget": "switch",
        },
    )
    """允许麦麦在回复开头 @ 一个或多个用户，由模型根据聊天内容决定是否使用。"""

    max_context_size: int = Field(
        default=50,
        json_schema_extra={
            "label": '群聊上下文',
            "x-widget": "input",
            "x-layout": "inline-right",
            "x-input-width": "6.5rem",
            "x-row": "chat-context-controls",
        },
    )
    """群聊回复时参考的最近消息数量；越大越懂上下文，也更耗模型。"""

    max_private_context_size: int = Field(
        default=75,
        json_schema_extra={
            "label": '私聊上下文',
            "x-widget": "input",
            "x-layout": "inline-right",
            "x-input-width": "6.5rem",
            "x-row": "chat-context-controls",
        },
    )
    """私聊回复时参考的最近消息数量。"""

    use_token_limit: bool = Field(
        default=False,
        json_schema_extra={
            "label": "群聊使用 Token 阈值",
            "x-widget": "switch",
            "x-row": "chat-token-mode",
        },
    )
    """开启后按 Planner 返回的实际输入 Token 用量触发上下文裁切与摘要，不再按群聊消息条数裁切。"""

    private_use_token_limit: bool = Field(
        default=False,
        json_schema_extra={
            "label": "私聊使用 Token 阈值",
            "x-widget": "switch",
            "x-row": "chat-token-mode",
        },
    )
    """开启后按 Planner 返回的实际输入 Token 用量触发上下文裁切与摘要，不再按私聊消息条数裁切。"""

    max_context_tokens: int = Field(
        default=128000,
        ge=16000,
        le=1000000,
        json_schema_extra={
            "label": "群聊 Token 阈值",
            "x-widget": "input",
            "x-layout": "inline-right",
            "x-input-width": "8rem",
            "x-row": "chat-token-limits",
        },
    )
    """群聊输入达到此 Token 数后裁切旧历史；Focus 共享组也使用此值。范围 16K–1M，单次请求可能超过阈值；模型不返回用量时不会按 Token 裁切。"""

    private_max_context_tokens: int = Field(
        default=128000,
        ge=16000,
        le=1000000,
        json_schema_extra={
            "label": "私聊 Token 阈值",
            "x-widget": "input",
            "x-layout": "inline-right",
            "x-input-width": "8rem",
            "x-row": "chat-token-limits",
        },
    )
    """私聊输入达到此 Token 数后裁切旧历史。范围 16K–1M，单次请求可能超过阈值；模型不返回用量时不会按 Token 裁切。"""

    context_compaction_summary_max_chars: int = Field(
        default=6000,
        ge=1000,
        le=8000,
        json_schema_extra={
            "label": '状态摘要字符上限',
            "x-widget": "input",
            "advanced": True,
        },
    )
    """滚动状态摘要的最大字符数；使用 utils 模型生成，摘要始终随 Planner 上下文发送。"""

    reply_timing: ChatReplyTimingConfig = Field(default_factory=ChatReplyTimingConfig)
    """什么时候回复、回复频率与等待退避配置。"""

    reply_style: ChatReplyStyleConfig = Field(default_factory=ChatReplyStyleConfig)
    """如何回复、引用回复与聊天 Prompt 配置。"""


class AttentionDriftConfig(ConfigBase):
    """注意力漂移实验功能配置。"""

    __ui_label__ = "注意力漂移"
    __ui_icon__ = "sparkles"

    enabled: bool = Field(
        default=False,
        json_schema_extra={
            "label": '注意力漂移模式',
            "x-widget": "switch",
        },
    )
    """开启后，麦麦会更容易被有趣的新话题、梗或反差点吸引，但仍需保持上下文可理解。"""

    drift_level: Literal["subtle", "active", "scattered", "wild"] = Field(
        default="scattered",
        json_schema_extra={
            "label": '漂移档位',
            "x-widget": "discrete-slider",
            "x-option-labels": ATTENTION_DRIFT_LEVEL_OPTION_LABELS,
            "x-option-descriptions": ATTENTION_DRIFT_LEVEL_OPTION_DESCRIPTIONS,
            "x-row": "attention-drift-style",
        },
    )
    """控制注意力漂移的整体表现档位，而不是用数值概率描述。"""

    anchor_policy: Literal["strict", "balanced", "loose"] = Field(
        default="balanced",
        json_schema_extra={
            "label": '回钩策略',
            "x-widget": "discrete-slider",
            "x-option-labels": ATTENTION_DRIFT_ANCHOR_OPTION_LABELS,
            "x-option-descriptions": ATTENTION_DRIFT_ANCHOR_OPTION_DESCRIPTIONS,
            "x-row": "attention-drift-style",
        },
    )
    """控制话题漂移后需要多强地回到当前聊天上下文。"""

    reaction_style: Literal["reserved", "natural", "lively"] = Field(
        default="lively",
        json_schema_extra={
            "label": '短反应风格',
            "x-widget": "discrete-slider",
            "x-option-labels": ATTENTION_DRIFT_REACTION_OPTION_LABELS,
            "x-option-descriptions": ATTENTION_DRIFT_REACTION_OPTION_DESCRIPTIONS,
            "x-row": "attention-drift-reaction",
        },
    )
    """控制短句、吐槽、语气词等短反应在漂移风格中的使用方式。"""


class GroupAttentionDriftConfig(AttentionDriftConfig):
    """群聊注意力漂移配置。"""

    __ui_label__ = "群聊注意力漂移"


class PrivateAttentionDriftConfig(AttentionDriftConfig):
    """私聊注意力漂移配置。"""

    __ui_label__ = "私聊注意力漂移"


class CapabilitiesConfig(ConfigBase):
    """能力配置类"""

    __ui_label__ = "能力"
    __ui_order__ = 30

    web_search_enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '联网搜索能力',
            "x-widget": "switch",
        },
    )
    """允许麦麦使用统一联网搜索工具；默认优先使用模型设置中已分配的联网搜索提供商，不可用时使用搜索引擎。关闭后停止提供搜索工具，不影响已配置的网页读取工具。"""

    web_search_priority: Literal["provider_first", "engine_first"] = Field(
        default="provider_first",
        json_schema_extra={
            "label": '联网搜索优先级',
            "x-widget": "select",
            "x-option-labels": {
                "provider_first": "联网搜索提供商优先",
                "engine_first": "搜索引擎优先",
            },
        },
    )
    """优先使用所选来源，调用失败或来源未配置时尝试另一来源；联网搜索提供商仍在模型设置中管理和分配。"""

    web_search_engine: Literal["google", "bing"] = Field(
        default="google",
        json_schema_extra={
            "label": '默认搜索引擎',
            "x-widget": "select",
            "x-option-labels": {"google": "Google", "bing": "Bing"},
        },
    )
    """搜索引擎直接访问公开搜索页面，默认引擎失败后尝试另一个引擎；与需要单独配置密钥的联网搜索提供商分开管理。"""

    web_search_proxy: str = Field(
        default="",
        json_schema_extra={
            "label": '搜索引擎代理',
            "x-widget": "input",
        },
    )
    """仅用于搜索引擎请求的代理地址，如 http://127.0.0.1:7890；留空使用当前网络环境。联网搜索提供商使用各自的连接配置。"""

    web_search_timeout: float = Field(
        default=20.0,
        gt=0,
        le=120,
        json_schema_extra={
            "label": '搜索引擎超时（秒）',
            "x-widget": "input",
        },
    )
    """单次搜索引擎请求的最长等待时间；超时后继续尝试其余搜索来源。"""

    files: bool = Field(
        default=False,
        json_schema_extra={
            "label": '文件功能',
            "x-widget": "switch",
        },
    )
    """启用聊天附件登记、文件工具、插件 SDK 和 WebUI 文件入口；默认关闭，不依赖 WebUI 或沙盒开关。关闭后拒绝新的文件操作，不删除已有原件。"""

    tool_result_condense: bool = Field(
        default=False,
        json_schema_extra={
            "label": '超长工具结果整理',
            "x-widget": "switch",
        },
    )
    """工具返回的结果超过阈值字数时，先交给子代理按 Planner 当前意图整理成结论再写入上下文，减少后续每轮的上下文占用；会多一次模型请求。"""

    tool_result_condense_threshold: int = Field(
        default=3000,
        ge=500,
        json_schema_extra={
            "advanced": True,
            "x-widget": "input",
            "label": '工具结果整理阈值',
        },
    )
    """工具结果达到多少字时才触发整理，仅在开启“超长工具结果整理”时生效；调低会更频繁地整理，调高则更多原文留在上下文里。"""

    planner_subagent: bool = Field(
        default=False,
        json_schema_extra={
            "label": '子代理任务派发',
            "x-widget": "switch",
        },
    )
    """给 Planner 提供 subagent 工具：把自包含的查询或整理任务交给子代理，子代理在独立上下文里多轮调用被授权的工具，只把结论交还给 Planner。"""

    advanced_sub_agent: bool = Field(
        default=False,
        json_schema_extra={
            "label": '高级子代理',
            "x-widget": "switch",
        },
    )
    """子代理改为在后台运行：派发后立刻返回任务 id，麦麦可以继续聊天，子代理结束时结论作为一条新消息送回并唤醒 Planner；同时提供查看和终止后台任务的工具。需要先开启“子代理任务派发”。"""


class ExperimentalConfig(ConfigBase):
    """实验性功能配置类"""

    __ui_label__ = "实验性功能"
    __ui_advanced__ = True
    __ui_order__ = 140

    passive_replyer: bool = Field(
        default=False,
        json_schema_extra={
            "label": '被动式 replyer',
            "x-widget": "switch",
        },
    )
    """仅作用于普通聊天模式：Planner 不调用工具而输出正文时，将正文作为自然语言指导启动一次回复；篇幅、表达偏好和插件相关需求直接写入指导，引用与附件由并行回复补充器编排。关闭时使用原有 reply 工具。切换从下一轮思考生效，Focus 不受影响。"""

    group_attention_drift: GroupAttentionDriftConfig = Field(
        default_factory=GroupAttentionDriftConfig,
        json_schema_extra={
            "label": '群聊注意力漂移',
        },
    )
    """群聊注意力漂移实验模式；让麦麦在群聊中表现出更活跃的联想和轻微话题漂移。"""

    private_attention_drift: PrivateAttentionDriftConfig = Field(
        default_factory=PrivateAttentionDriftConfig,
        json_schema_extra={
            "label": '私聊注意力漂移',
        },
    )
    """私聊注意力漂移实验模式；让麦麦在私聊中表现出更活跃的联想和轻微话题漂移。"""

    focus_mode: bool = Field(
        default=False,
        json_schema_extra={
            "label": 'Focus 模式',
            "x-widget": "switch",
        },
    )
    """让同组聊天共享一个持续思考的 Planner；全部消息共同进入上下文，工具通过 session_id 指定处理目标。"""

    focus_on_private: bool = Field(
        default=False,
        json_schema_extra={
            "label": '私聊启用 Focus',
            "x-widget": "switch",
        },
    )
    """Focus 模式是否也作用于私聊。"""

    focus_chat_whitelist: list["TargetItem"] = Field(
        default_factory=list,
        json_schema_extra={
            "label": 'Focus 白名单',
            "x-widget": "custom",
        },
    )
    """_wrap_Focus 白名单。配置后只有命中的群聊或私聊会进入 Focus；留空表示所有符合聊天类型开关的聊天都可进入 Focus。"""

    focus_groups: list["ChatStreamGroup"] = Field(
        default_factory=list,
        json_schema_extra={
            "label": 'Focus 共享组',
            "x-widget": "custom",
        },
    )
    """_wrap_同组聊天共享 Planner 与完整上下文，不同组独立运行；未匹配的聊天各自形成独立组。"""


class MessageReceiveConfig(ConfigBase):
    """消息接收配置类"""

    __ui_label__ = "消息接收"
    __ui_advanced__ = True
    __ui_order__ = 70

    ban_words: set[str] = Field(
        default_factory=lambda: set(),
        json_schema_extra={
            "x-widget": "custom",
        },
    )
    """包含这些词的消息会被过滤，不进入麦麦处理。"""

    ban_msgs_regex: set[str] = Field(
        default_factory=lambda: set(),
        json_schema_extra={
            "x-widget": "custom",
        },
    )
    """用正则过滤消息；适合更复杂的过滤规则。"""

    def model_post_init(self, context: Optional[dict] = None) -> None:
        for pattern in self.ban_msgs_regex:
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"Invalid regex pattern in ban_msgs_regex: '{pattern}'") from e
        return super().model_post_init(context)


class TargetItem(ConfigBase):
    platform: str = Field(
        default="",
        json_schema_extra={
            "label": '平台',
            "x-widget": "input",
        },
    )
    """要单独配置的平台；和聊天流 ID 都留空表示全局默认，仅平台有值且聊天流 ID 留空表示平台兜底。"""

    item_id: str = Field(
        default="",
        json_schema_extra={
            "label": '聊天流 ID',
            "x-widget": "input",
        },
    )
    """用户/群 ID；留空时和平台字段共同决定全局默认或平台兜底，* 表示任意聊天流。"""

    rule_type: Literal["group", "private"] = Field(
        default="group",
        json_schema_extra={
            "label": '聊天类型',
            "x-widget": "select",
            "x-option-descriptions": RULE_TYPE_OPTION_DESCRIPTIONS,
        },
    )
    """聊天流类型，group（群聊）或private（私聊）"""


class ChatStreamGroup(ConfigBase):
    """聊天流共享组配置类"""

    targets: list[TargetItem] = Field(
        default_factory=lambda: [],
        json_schema_extra={
            "label": '共享聊天流',
            "x-widget": "custom",
        },
    )
    """_wrap_这个组里的聊天流会共享对应的学习内容。"""


class AMemorixIntegrationConfig(ConfigBase):
    """记忆在聊天中的使用"""

    __ui_parent__ = "a_memorix"

    enable_memory_query_tool: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用记忆检索',
            "x-widget": "switch",
        },
    )
    """是否允许麦麦在聊天时查询长期记忆"""

    memory_query_default_limit: int = Field(
        default=5,
        ge=1,
        le=20,
        json_schema_extra={
            "label": '回忆记忆条数',
            "x-widget": "input",
        },
    )
    """每次默认从长期记忆中取回多少条结果"""

    enable_person_profile_query_tool: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用人物画像查询',
            "x-widget": "switch",
        },
    )
    """是否允许麦麦查询人物画像记忆"""

    enable_person_profile_injection: bool = Field(
        default=True,
        json_schema_extra={
            "label": '自动注入人物画像',
            "x-widget": "switch",
        },
    )
    """是否在 Maisaka Planner 调用前自动注入当前对象相关的人物画像"""

    person_profile_injection_max_profiles: int = Field(
        default=3,
        ge=1,
        le=5,
        json_schema_extra={
            "label": '注入画像上限',
            "x-widget": "input",
        },
    )
    """每轮自动注入的人物画像数量上限"""

    heuristic_memory_recall_enabled: bool = Field(
        default=False,
        json_schema_extra={
            "label": '启发式拉起记忆',
            "x-widget": "switch",
        },
    )
    """是否根据最近聊天消息自然拉起长期记忆"""

    heuristic_memory_cross_chat_enabled: bool = Field(
        default=False,
        json_schema_extra={
            "label": '允许跨聊天流拉起',
            "x-widget": "switch",
        },
    )
    """是否允许启发式记忆从其他聊天流召回候选"""

    heuristic_memory_recall_window_size: int = Field(
        default=20,
        ge=1,
        le=200,
        json_schema_extra={
            "label": '召回窗口消息数',
            "x-widget": "input",
            "advanced": True,
        },
    )
    """构建轻量召回查询时读取的最近消息数量，查询最多保留最近的 1000 字符"""

    heuristic_memory_recall_limit: int = Field(
        default=3,
        ge=1,
        le=10,
        json_schema_extra={
            "label": '自然拉起记忆条数',
            "x-widget": "input",
            "advanced": True,
        },
    )
    """每轮自然拉起的长期记忆数量上限"""

    heuristic_memory_recall_max_chars: int = Field(
        default=900,
        ge=100,
        le=4000,
        json_schema_extra={
            "label": '自然拉起文本上限',
            "x-widget": "input",
            "advanced": True,
        },
    )
    """自然拉起记忆注入文本的最大字符数"""

    heuristic_memory_recall_min_interval_seconds: int = Field(
        default=180,
        ge=0,
        json_schema_extra={
            "label": '自然拉起冷却秒数',
            "x-widget": "input",
            "advanced": True,
        },
    )
    """同一聊天流两次自然拉起的最小间隔秒数"""

    heuristic_memory_recall_min_new_messages: int = Field(
        default=60,
        ge=1,
        json_schema_extra={
            "label": '自然拉起新增消息阈值',
            "x-widget": "input",
            "advanced": True,
        },
    )
    """两次自然拉起之间至少需要新增的当前聊天流消息数"""

    heuristic_memory_recall_cache_ttl_seconds: int = Field(
        default=300,
        ge=0,
        json_schema_extra={
            "label": '自然拉起缓存秒数',
            "x-widget": "input",
            "advanced": True,
        },
    )
    """同一聊天流自然拉起结果的运行时缓存时间"""

    heuristic_memory_group_to_private_enabled: bool = Field(
        default=False,
        json_schema_extra={
            "label": '私聊拉起群聊记忆',
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """私聊中是否允许自然拉起群聊记忆"""

    heuristic_memory_private_to_group_enabled: bool = Field(
        default=False,
        json_schema_extra={
            "label": '群聊拉起私聊记忆',
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """群聊中是否允许自然拉起私聊记忆"""

    person_fact_writeback_enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '写回人物事实',
            "x-widget": "switch",
        },
    )
    """是否在发送回复后自动提取并写回人物事实到长期记忆"""

    chat_summary_writeback_enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '写回聊天摘要',
            "x-widget": "switch",
        },
    )
    """是否在 Maisaka 聊天过程中按消息窗口自动写回聊天摘要到长期记忆"""

    chat_summary_writeback_message_threshold: int = Field(
        default=36,
        ge=1,
        json_schema_extra={
            "x-widget": "input",
            "advanced": True,
        },
    )
    """自动写回聊天摘要的消息窗口阈值"""

    chat_summary_writeback_context_length: int = Field(
        default=36,
        ge=1,
        le=500,
        json_schema_extra={
            "x-widget": "input",
            "advanced": True,
        },
    )
    """自动写回聊天摘要时，从聊天流中回看的消息条数"""

    fuzzy_modify_enabled: bool = Field(
        default=True,
        json_schema_extra={
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """是否启用自然语言记忆修正的后台接口"""

    fuzzy_modify_auto_execute_enabled: bool = Field(
        default=False,
        json_schema_extra={
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """是否允许高置信记忆修正跳过人工确认自动执行"""

    fuzzy_modify_confirm_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "x-widget": "slider",
            "step": 0.01,
            "advanced": True,
        },
    )
    """记忆修正建议进入自动确认判定时使用的置信度阈值"""

    fuzzy_modify_candidate_limit: int = Field(
        default=20,
        ge=1,
        le=100,
        json_schema_extra={
            "x-widget": "input",
            "advanced": True,
        },
    )
    """每次记忆修正交给 LLM 的候选记忆上限"""

    fuzzy_modify_max_targets: int = Field(
        default=5,
        ge=1,
        le=20,
        json_schema_extra={
            "x-widget": "input",
            "advanced": True,
        },
    )
    """单个记忆修正计划允许标记失效的旧记忆上限"""

    fuzzy_modify_allow_global_scope: bool = Field(
        default=False,
        json_schema_extra={
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """未指定聊天流时，是否允许在全局记忆范围内做记忆修正候选检索"""

    feedback_correction_enabled: bool = Field(
        default=False,
        json_schema_extra={
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """是否启用反馈驱动的延迟记忆纠错任务"""

    feedback_correction_window_hours: float = Field(
        default=12.0,
        ge=0.1,
        json_schema_extra={
            "x-widget": "input",
            "advanced": True,
        },
    )
    """反馈窗口时长（小时），以 query_memory 执行时间为起点"""

    feedback_correction_check_interval_minutes: int = Field(
        default=30,
        ge=1,
        json_schema_extra={
            "x-widget": "input",
            "advanced": True,
        },
    )
    """反馈纠错定时任务轮询间隔（分钟）"""

    feedback_correction_batch_size: int = Field(
        default=20,
        ge=1,
        le=200,
        json_schema_extra={
            "x-widget": "input",
            "advanced": True,
        },
    )
    """反馈纠错每轮最大处理任务数"""

    feedback_correction_auto_apply_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "x-widget": "slider",
            "step": 0.01,
            "advanced": True,
        },
    )
    """自动应用纠错动作的最低置信度阈值"""

    feedback_correction_max_feedback_messages: int = Field(
        default=30,
        ge=1,
        le=200,
        json_schema_extra={
            "x-widget": "input",
            "advanced": True,
        },
    )
    """每个纠错任务最多使用的窗口内用户反馈消息数"""

    feedback_correction_prefilter_enabled: bool = Field(
        default=True,
        json_schema_extra={
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """是否启用纠错前置预筛（用于减少不必要的模型调用）"""

    feedback_correction_paragraph_mark_enabled: bool = Field(
        default=True,
        json_schema_extra={
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """是否为受影响 paragraph 写入已纠正旧事实标记"""

    feedback_correction_paragraph_hard_filter_enabled: bool = Field(
        default=True,
        json_schema_extra={
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """是否在用户侧查询中硬过滤带有 stale 标记的 paragraph"""

    feedback_correction_profile_refresh_enabled: bool = Field(
        default=True,
        json_schema_extra={
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """是否在反馈纠错后将受影响人物画像加入刷新队列"""

    feedback_correction_profile_force_refresh_on_read: bool = Field(
        default=True,
        json_schema_extra={
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """人物画像处于脏队列时，读取是否强制刷新而不直接复用旧快照"""

    feedback_correction_episode_rebuild_enabled: bool = Field(
        default=True,
        json_schema_extra={
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """是否在反馈纠错后将受影响 source 加入 episode 重建队列"""

    feedback_correction_episode_query_block_enabled: bool = Field(
        default=True,
        json_schema_extra={
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """episode source 处于重建队列时，是否对用户侧查询做屏蔽"""

    feedback_correction_reconcile_interval_minutes: int = Field(
        default=5,
        ge=1,
        json_schema_extra={
            "x-widget": "input",
            "advanced": True,
        },
    )
    """反馈纠错二阶段一致性后台协调任务轮询间隔（分钟）"""

    feedback_correction_reconcile_batch_size: int = Field(
        default=20,
        ge=1,
        le=200,
        json_schema_extra={
            "x-widget": "input",
            "advanced": True,
        },
    )
    """反馈纠错二阶段一致性每轮处理 profile/episode 队列的批大小"""

    def model_post_init(self, context: Optional[dict] = None) -> None:
        """验证配置值"""
        if not 0 <= self.fuzzy_modify_confirm_threshold <= 1:
            raise ValueError(
                "fuzzy_modify_confirm_threshold 必须在 [0, 1] 之间，"
                f"当前值: {self.fuzzy_modify_confirm_threshold}"
            )
        if self.fuzzy_modify_candidate_limit < 1:
            raise ValueError(
                "fuzzy_modify_candidate_limit 必须至少为1，"
                f"当前值: {self.fuzzy_modify_candidate_limit}"
            )
        if self.fuzzy_modify_max_targets < 1:
            raise ValueError(
                f"fuzzy_modify_max_targets 必须至少为1，当前值: {self.fuzzy_modify_max_targets}"
            )
        if self.feedback_correction_window_hours <= 0:
            raise ValueError(
                f"feedback_correction_window_hours 必须大于0，当前值: {self.feedback_correction_window_hours}"
            )
        if self.feedback_correction_check_interval_minutes < 1:
            raise ValueError(
                "feedback_correction_check_interval_minutes 必须至少为1，"
                f"当前值: {self.feedback_correction_check_interval_minutes}"
            )
        if self.feedback_correction_batch_size < 1:
            raise ValueError(
                f"feedback_correction_batch_size 必须至少为1，当前值: {self.feedback_correction_batch_size}"
            )
        if not 0 <= self.feedback_correction_auto_apply_threshold <= 1:
            raise ValueError(
                "feedback_correction_auto_apply_threshold 必须在 [0, 1] 之间，"
                f"当前值: {self.feedback_correction_auto_apply_threshold}"
            )
        if self.feedback_correction_max_feedback_messages < 1:
            raise ValueError(
                "feedback_correction_max_feedback_messages 必须至少为1，"
                f"当前值: {self.feedback_correction_max_feedback_messages}"
            )
        if self.feedback_correction_reconcile_interval_minutes < 1:
            raise ValueError(
                "feedback_correction_reconcile_interval_minutes 必须至少为1，"
                f"当前值: {self.feedback_correction_reconcile_interval_minutes}"
            )
        if self.feedback_correction_reconcile_batch_size < 1:
            raise ValueError(
                "feedback_correction_reconcile_batch_size 必须至少为1，"
                f"当前值: {self.feedback_correction_reconcile_batch_size}"
            )
        return super().model_post_init(context)


class AMemorixPluginConfig(ConfigBase):
    """记忆系统  A-Memorix"""

    enabled: bool = Field(
        default=False,
        json_schema_extra={
            "label": '启用记忆',
        },
    )
    """是否启用长期记忆系统"""


class AMemorixStorageConfig(ConfigBase):
    """A_Memorix 存储位置"""

    data_dir: str = Field(
        default="data/a-memorix",
        json_schema_extra={
            "label": '数据目录',
        },
    )
    """数据目录"""


class AMemorixImageMemoryConfig(ConfigBase):
    """A_Memorix 图片资产、向量任务和相似召回配置。"""

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用图片记忆'
        },
    )
    task_name: str = Field(
        default="image_embedding",
        json_schema_extra={
            "label": '图片嵌入任务'
        },
    )
    preprocess_version: str = Field(
        default="identity_v1",
        json_schema_extra={"label": '预处理版本'},
    )
    probe_retry_seconds: float = Field(
        default=60.0,
        ge=0.0,
        json_schema_extra={
            "label": '模型探测重试间隔'
        },
    )
    max_bytes: int = Field(
        default=10 * 1024 * 1024,
        ge=1,
        json_schema_extra={"label": '单图大小上限'},
    )
    max_pixels: int = Field(
        default=40_000_000,
        ge=1,
        json_schema_extra={"label": '单图像素上限'},
    )
    candidate_limit: int = Field(
        default=8,
        ge=1,
        le=100,
        json_schema_extra={"label": '相似候选数量'},
    )
    similarity_threshold: float = Field(
        default=0.72,
        ge=-1.0,
        le=1.0,
        json_schema_extra={"label": '相似度阈值'},
    )
    job_poll_interval_seconds: float = Field(
        default=2.0,
        ge=0.1,
        json_schema_extra={"label": '任务轮询间隔'},
    )
    job_batch_size: int = Field(
        default=4,
        ge=1,
        le=100,
        json_schema_extra={"label": '任务处理批量'},
    )
    job_enqueue_batch_size: int = Field(
        default=200,
        ge=1,
        json_schema_extra={"label": '任务入队批量'},
    )
    job_lease_seconds: float = Field(
        default=120.0,
        ge=1.0,
        json_schema_extra={"label": '任务租约秒数'},
    )
    job_max_retries: int = Field(
        default=5,
        ge=0,
        json_schema_extra={"label": '任务最大重试'},
    )
    min_train_threshold: int = Field(
        default=40,
        ge=1,
        json_schema_extra={"label": '索引训练最小样本'},
    )


class AMemorixEmbeddingFallbackConfig(ConfigBase):
    """A_Memorix Embedding 回退"""

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用回退',
        },
    )
    """是否启用回退机制"""

    probe_interval_seconds: int = Field(
        default=180,
        ge=10,
        json_schema_extra={
            "label": '探测间隔',
        },
    )
    """探测间隔秒数"""

    allow_metadata_only_write: bool = Field(
        default=True,
        json_schema_extra={
            "label": '允许仅写元数据',
        },
    )
    """是否允许仅写入元数据"""


class AMemorixParagraphVectorBackfillConfig(ConfigBase):
    """A_Memorix 段落向量回填"""

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用回填',
        },
    )
    """是否启用回填任务"""

    interval_seconds: int = Field(
        default=60,
        ge=5,
        json_schema_extra={
            "label": '回填间隔',
        },
    )
    """回填轮询间隔"""

    batch_size: int = Field(
        default=64,
        ge=1,
        json_schema_extra={
            "label": '批量大小',
        },
    )
    """单批回填数量"""

    max_retry: int = Field(
        default=5,
        ge=0,
        json_schema_extra={
            "label": '最大重试',
        },
    )
    """最大重试次数"""


class AMemorixEmbeddingConfig(ConfigBase):
    """记忆向量化配置"""

    model_name: str = Field(
        default="auto",
        json_schema_extra={
            "label": '向量化模型',
        },
    )
    """用于把记忆内容转换成向量的模型，auto 表示自动选择"""

    dimension: int = Field(
        default=1024,
        ge=1,
        json_schema_extra={
            "label": '向量维度',
        },
    )
    """记忆向量的维度，需要与向量化模型保持一致"""

    dimension_request_mode: Literal["explicit", "always", "never"] = Field(
        default="explicit",
        json_schema_extra={
            "label": '维度请求模式',
        },
    )
    """是否在 embedding 请求中携带维度参数：explicit 仅显式指定时携带，always 总是携带，never 不携带"""

    batch_size: int = Field(
        default=32,
        ge=1,
        json_schema_extra={
            "label": '单批数量',
        },
    )
    """每次向量化请求处理的记忆条数"""

    max_concurrent: int = Field(
        default=5,
        ge=1,
        json_schema_extra={
            "label": '最大并发数',
        },
    )
    """同时进行的向量化请求数量"""

    enable_cache: bool = Field(
        default=False,
        json_schema_extra={
            "label": '启用向量缓存',
        },
    )
    """是否缓存向量化结果"""

    runtime_train_threshold: int = Field(
        default=256,
        ge=1,
        json_schema_extra={
            "label": '运行期向量训练阈值',
        },
    )
    """未训练向量池在运行期间触发 SQ8 后台训练所需的最少向量数"""

    quantization_type: Literal["int8"] = Field(
        default="int8",
        json_schema_extra={
            "label": '量化方式',
        },
    )
    """向量压缩方式，当前仅支持 int8(SQ8)"""

    fallback: AMemorixEmbeddingFallbackConfig = Field(
        default_factory=AMemorixEmbeddingFallbackConfig,
        json_schema_extra={
            "label": 'Embedding 回退',
        },
    )
    """Embedding 回退配置"""

    paragraph_vector_backfill: AMemorixParagraphVectorBackfillConfig = Field(
        default_factory=AMemorixParagraphVectorBackfillConfig,
        json_schema_extra={
            "label": '段落向量回填',
        },
    )
    """段落向量回填配置"""


class AMemorixSparseRetrievalConfig(ConfigBase):
    """A_Memorix 稀疏检索配置"""

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用稀疏检索',
        },
    )
    """是否启用稀疏检索"""

    backend: Literal["fts5"] = Field(
        default="fts5",
        json_schema_extra={
            "label": '检索后端',
        },
    )
    """稀疏检索后端"""

    mode: Literal["auto", "fallback_only", "hybrid"] = Field(
        default="auto",
        json_schema_extra={
            "label": '检索模式',
        },
    )
    """稀疏检索模式"""

    tokenizer_mode: Literal["jieba", "mixed", "char_2gram"] = Field(
        default="jieba",
        json_schema_extra={
            "label": '分词模式',
        },
    )
    """分词模式"""

    candidate_k: int = Field(
        default=80,
        ge=1,
        json_schema_extra={
            "label": '段落候选数',
        },
    )
    """段落候选数"""

    relation_candidate_k: int = Field(
        default=60,
        ge=1,
        json_schema_extra={
            "label": '关系候选数',
        },
    )
    """关系候选数"""


class AMemorixSmartFallbackConfig(ConfigBase):
    """A_Memorix 智能兜底检索配置"""

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用智能兜底',
        },
    )
    """是否启用智能兜底检索"""


class AMemorixRetrievalSearchConfig(ConfigBase):
    """A_Memorix 搜索后处理配置"""

    smart_fallback: AMemorixSmartFallbackConfig = Field(
        default_factory=AMemorixSmartFallbackConfig,
        json_schema_extra={
            "label": '智能兜底',
        },
    )
    """智能兜底检索配置"""


class AMemorixFusionRetrievalConfig(ConfigBase):
    """A_Memorix 检索融合配置"""

    method: Literal["weighted_rrf", "alpha_legacy"] = Field(
        default="weighted_rrf",
        json_schema_extra={
            "label": '融合方法',
        },
    )
    """检索融合方法"""

    rrf_k: int = Field(
        default=60,
        ge=1,
        json_schema_extra={
            "label": 'RRF K',
        },
    )
    """RRF 融合参数"""

    vector_weight: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "label": '向量权重',
        },
    )
    """向量检索权重"""

    bm25_weight: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "label": 'BM25 权重',
        },
    )
    """BM25 稀疏检索权重"""


class AMemorixRelationVectorizationConfig(ConfigBase):
    """A_Memorix 关系向量化配置"""

    enabled: bool = Field(
        default=False,
        json_schema_extra={
            "label": '启用关系向量',
        },
    )
    """是否启用关系向量化"""

    backfill_enabled: bool = Field(
        default=False,
        json_schema_extra={
            "label": '启用关系向量回填',
        },
    )
    """是否启用关系向量回填"""

    write_on_import: bool = Field(
        default=True,
        json_schema_extra={
            "label": '导入时写入关系向量',
        },
    )
    """导入时是否写入关系向量"""


class AMemorixRelationIntentVectorPoolConfig(ConfigBase):
    """A_Memorix 关系意图下的双向量池配置"""

    graph_top_k: int = Field(
        default=80,
        ge=1,
        json_schema_extra={
            "label": '关系意图图谱候选数',
        },
    )
    """关系意图命中时的图谱池候选数"""

    semantic_weight: float = Field(
        default=0.45,
        ge=0.0,
        json_schema_extra={
            "label": '关系意图语义权重',
        },
    )
    """关系意图命中时的段落语义权重"""

    sparse_weight: float = Field(
        default=0.15,
        ge=0.0,
        json_schema_extra={
            "label": '关系意图稀疏权重',
        },
    )
    """关系意图命中时的稀疏检索权重"""

    graph_weight: float = Field(
        default=0.40,
        ge=0.0,
        json_schema_extra={
            "label": '关系意图图谱权重',
        },
    )
    """关系意图命中时的图谱证据权重"""

    return_relation_items: bool = Field(
        default=False,
        json_schema_extra={
            "label": '返回独立关系项',
        },
    )
    """关系意图命中时是否返回独立关系结果"""


class AMemorixVectorPoolsConfig(ConfigBase):
    """A_Memorix 双向量池检索配置"""

    mode: Literal["single", "dual"] = Field(
        default="dual",
        json_schema_extra={
            "label": '向量池模式',
        },
    )
    """向量池模式"""

    paragraph_top_k: int = Field(
        default=20,
        ge=1,
        json_schema_extra={
            "label": '段落池候选数',
        },
    )
    """段落向量池候选数"""

    graph_top_k: int = Field(
        default=40,
        ge=1,
        json_schema_extra={
            "label": '图谱池候选数',
        },
    )
    """图谱向量池候选数"""

    graph_expand_paragraph_k: int = Field(
        default=80,
        ge=1,
        json_schema_extra={
            "label": '图谱展开段落上限',
        },
    )
    """图谱证据展开段落上限"""

    relation_expand_per_hit: int = Field(
        default=5,
        ge=1,
        json_schema_extra={
            "label": '每个关系展开段落数',
        },
    )
    """每个关系命中最多展开的段落数"""

    entity_expand_per_hit: int = Field(
        default=8,
        ge=1,
        json_schema_extra={
            "label": '每个实体展开段落数',
        },
    )
    """每个实体命中最多展开的段落数"""

    relation_evidence_weight: float = Field(
        default=1.0,
        ge=0.0,
        json_schema_extra={
            "label": '关系证据权重',
        },
    )
    """关系证据分权重"""

    entity_evidence_weight: float = Field(
        default=0.55,
        ge=0.0,
        json_schema_extra={
            "label": '实体证据权重',
        },
    )
    """实体证据分权重"""

    semantic_weight: float = Field(
        default=0.65,
        ge=0.0,
        json_schema_extra={
            "label": '段落语义权重',
        },
    )
    """段落语义分权重"""

    sparse_weight: float = Field(
        default=0.20,
        ge=0.0,
        json_schema_extra={
            "label": '稀疏检索权重',
        },
    )
    """稀疏检索分权重"""

    graph_weight: float = Field(
        default=0.15,
        ge=0.0,
        json_schema_extra={
            "label": '图谱证据权重',
        },
    )
    """图谱证据分权重"""

    relation_intent: AMemorixRelationIntentVectorPoolConfig = Field(
        default_factory=AMemorixRelationIntentVectorPoolConfig,
        json_schema_extra={
            "label": '关系意图权重',
        },
    )
    """关系意图命中时的双向量池配置"""


class AMemorixRetrievalConfig(ConfigBase):
    """A_Memorix 检索配置"""

    top_k_paragraphs: int = Field(
        default=20,
        ge=1,
        json_schema_extra={
            "label": '段落 Top-K',
        },
    )
    """段落候选数"""

    top_k_relations: int = Field(
        default=10,
        ge=1,
        json_schema_extra={
            "label": '关系 Top-K',
        },
    )
    """关系候选数"""

    top_k_final: int = Field(
        default=10,
        ge=1,
        json_schema_extra={
            "label": '最终 Top-K',
        },
    )
    """最终返回条数"""

    alpha: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "label": '关系融合权重',
        },
    )
    """关系融合权重"""

    enable_ppr: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用 PPR',
        },
    )
    """是否启用 PPR"""

    ppr_alpha: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "label": 'PPR Alpha',
        },
    )
    """PPR alpha"""

    ppr_timeout_seconds: float = Field(
        default=1.5,
        ge=0.1,
        json_schema_extra={
            "label": 'PPR 超时',
        },
    )
    """PPR 超时秒数"""

    ppr_concurrency_limit: int = Field(
        default=4,
        ge=1,
        json_schema_extra={
            "label": 'PPR 并发限制',
        },
    )
    """PPR 并发限制"""

    enable_parallel: bool = Field(
        default=True,
        json_schema_extra={
            "label": '并行检索',
        },
    )
    """是否启用并行检索"""

    search: AMemorixRetrievalSearchConfig = Field(
        default_factory=AMemorixRetrievalSearchConfig,
        json_schema_extra={
            "label": '搜索后处理',
        },
    )
    """搜索后处理配置"""

    fusion: AMemorixFusionRetrievalConfig = Field(
        default_factory=AMemorixFusionRetrievalConfig,
        json_schema_extra={
            "label": '检索融合',
        },
    )
    """检索融合配置"""

    relation_vectorization: AMemorixRelationVectorizationConfig = Field(
        default_factory=AMemorixRelationVectorizationConfig,
        json_schema_extra={
            "label": '关系向量化',
        },
    )
    """关系向量化配置"""

    vector_pools: AMemorixVectorPoolsConfig = Field(
        default_factory=AMemorixVectorPoolsConfig,
        json_schema_extra={
            "label": '向量池检索',
        },
    )
    """双向量池检索配置"""

    sparse: AMemorixSparseRetrievalConfig = Field(
        default_factory=AMemorixSparseRetrievalConfig,
        json_schema_extra={
            "label": '稀疏检索',
        },
    )
    """稀疏检索配置"""


class AMemorixThresholdConfig(ConfigBase):
    """A_Memorix 阈值过滤配置"""

    min_threshold: float = Field(
        default=0.29,
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "label": '最小阈值',
        },
    )
    """最小阈值"""

    max_threshold: float = Field(
        default=0.95,
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "label": '最大阈值',
        },
    )
    """最大阈值"""

    percentile: int = Field(
        default=75,
        ge=0,
        le=100,
        json_schema_extra={
            "label": '动态百分位',
        },
    )
    """动态阈值百分位"""

    min_results: int = Field(
        default=4,
        ge=1,
        json_schema_extra={
            "label": '最小保留数',
        },
    )
    """最小保留条数"""

    def model_post_init(self, context: Optional[dict] = None) -> None:
        if self.min_threshold >= self.max_threshold:
            raise ValueError("min_threshold 必须小于 max_threshold")
        return super().model_post_init(context)

class AMemorixRetrievalSubtypeFilterConfig(ConfigBase):
    """A_Memorix 跨聊天流检索结果分类型过滤配置"""

    enabled: bool = Field(
        default=False,
        json_schema_extra={
            "label": '启用跨聊天流过滤',
        },
    )
    """是否启用当前检索结果类型的跨聊天流过滤"""

    mode: Literal["blacklist", "whitelist"] = Field(
        default="blacklist",
        json_schema_extra={
            "label": '过滤模式',
        },
    )
    """过滤模式"""

    chats: list[str] = Field(
        default_factory=lambda: [],
        json_schema_extra={
            "label": '聊天流列表',
        },
    )
    """聊天流列表"""


class AMemorixRetrievalFilterConfig(ConfigBase):
    """A_Memorix 跨聊天流检索结果后置过滤配置"""

    chat_stream: AMemorixRetrievalSubtypeFilterConfig = Field(
        default_factory=AMemorixRetrievalSubtypeFilterConfig,
        json_schema_extra={
            "label": '普通聊天流记忆',
            "x-collapsed-by-default": True,
        },
    )
    """普通 paragraph/relation 命中的跨聊天流检索后置过滤"""

    chat_summary: AMemorixRetrievalSubtypeFilterConfig = Field(
        default_factory=AMemorixRetrievalSubtypeFilterConfig,
        json_schema_extra={
            "label": '聊天总结记忆',
            "x-collapsed-by-default": True,
        },
    )
    """聊天总结命中的跨聊天流检索后置过滤"""

    episode: AMemorixRetrievalSubtypeFilterConfig = Field(
        default_factory=AMemorixRetrievalSubtypeFilterConfig,
        json_schema_extra={
            "label": 'Episode 记忆',
            "x-collapsed-by-default": True,
        },
    )
    """Episode 命中的跨聊天流检索后置过滤"""


class AMemorixFilterConfig(ConfigBase):
    """聊天过滤配置"""

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用聊天过滤',
        },
    )
    """是否启用聊天过滤"""

    mode: Literal["blacklist", "whitelist"] = Field(
        default="blacklist",
        json_schema_extra={
            "label": '过滤模式',
        },
    )
    """过滤模式"""

    chats: list[str] = Field(
        default_factory=lambda: [],
        json_schema_extra={
            "label": '聊天流列表',
        },
    )
    """聊天流列表"""

    retrieval: AMemorixRetrievalFilterConfig = Field(
        default_factory=AMemorixRetrievalFilterConfig,
        json_schema_extra={
            "label": '跨聊天流检索结果过滤',
            "x-collapsed-by-default": True,
        },
    )
    """仅对跨聊天流检索结果生效的分类型过滤，不影响本聊天流读取自身记忆、写入和后台生成"""


class AMemorixEpisodeConfig(ConfigBase):
    """A_Memorix Episode 配置"""

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用 Episode',
        },
    )
    """是否启用 Episode"""

    generation_enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '自动生成 Episode',
        },
    )
    """是否启用自动生成"""

    source_poll_interval_seconds: float = Field(
        default=1.0,
        ge=0.1,
        json_schema_extra={
            "label": '来源任务轮询间隔',
        },
    )
    """来源级 Episode 任务轮询间隔秒数"""

    source_batch_size: int = Field(
        default=20,
        ge=1,
        json_schema_extra={
            "label": '来源任务批量',
        },
    )
    """单轮领取的来源任务数"""

    source_max_retry: int = Field(
        default=3,
        ge=1,
        json_schema_extra={
            "label": '来源任务最大尝试次数',
        },
    )
    """每个来源版本的最大尝试次数，包含首次尝试"""

    source_lease_seconds: float = Field(
        default=1800.0,
        ge=1.0,
        json_schema_extra={
            "label": '来源任务租约时长',
        },
    )
    """来源任务租约时长秒数"""

    source_max_wait_seconds: float = Field(
        default=60.0,
        ge=0.0,
        json_schema_extra={
            "label": '来源任务最大防抖等待',
        },
    )
    """来源持续写入时允许的最大防抖等待秒数"""

    max_paragraphs_per_call: int = Field(
        default=20,
        ge=1,
        json_schema_extra={
            "label": '单次段落上限',
        },
    )
    """单次最大段落数"""

    max_chars_per_call: int = Field(
        default=6000,
        ge=100,
        json_schema_extra={
            "label": '单次字符上限',
        },
    )
    """单次最大字符数"""

    source_time_window_hours: float = Field(
        default=24.0,
        ge=0.0,
        json_schema_extra={
            "label": '来源时间窗口',
        },
    )
    """时间窗口小时数"""

    segmentation_model: str = Field(
        default="auto",
        json_schema_extra={
            "label": '分段模型',
        },
    )
    """分段模型选择"""

    disabled_source_types: List[str] = Field(
        default_factory=lambda: ["person_fact"],
        json_schema_extra={
            "label": '跳过来源类型',
            "advanced": True,
        },
    )
    """自动生成 Episode 时跳过的来源类型"""


class AMemorixPersonProfileConfig(ConfigBase):
    """人物画像配置"""

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用人物画像',
        },
    )
    """是否启用画像"""

    refresh_interval_minutes: int = Field(
        default=30,
        ge=1,
        json_schema_extra={
            "label": '刷新间隔',
        },
    )
    """刷新间隔分钟数"""

    active_window_hours: float = Field(
        default=72.0,
        ge=1.0,
        json_schema_extra={
            "label": '活跃窗口',
        },
    )
    """活跃窗口小时数"""

    max_refresh_per_cycle: int = Field(
        default=50,
        ge=1,
        json_schema_extra={
            "label": '单轮刷新上限',
        },
    )
    """单轮最大刷新数"""

    refresh_debounce_seconds: int = Field(
        default=120,
        ge=0,
        json_schema_extra={
            "label": '刷新静默期',
            "advanced": True,
        },
    )
    """写入触发画像刷新前等待的静默秒数"""

    refresh_queue_interval_seconds: int = Field(
        default=60,
        ge=1,
        json_schema_extra={
            "label": '刷新队列间隔',
            "advanced": True,
        },
    )
    """画像刷新队列扫描间隔秒数"""

    refresh_queue_batch_size: int = Field(
        default=10,
        ge=1,
        json_schema_extra={
            "label": '刷新队列批量',
            "advanced": True,
        },
    )
    """画像刷新队列单轮处理人数"""

    refresh_retry_backoff_seconds: int = Field(
        default=300,
        ge=0,
        json_schema_extra={
            "label": '刷新重试等待',
            "advanced": True,
        },
    )
    """画像刷新失败后再次重试前等待的秒数"""

    max_retry: int = Field(
        default=3,
        ge=0,
        json_schema_extra={
            "label": '刷新最大重试',
            "advanced": True,
        },
    )
    """画像刷新队列最大重试次数"""

    top_k_evidence: int = Field(
        default=12,
        ge=1,
        json_schema_extra={
            "label": '证据条数',
        },
    )
    """证据条数"""

    evidence_classification_max_tokens: int = Field(
        default=1200,
        ge=128,
        json_schema_extra={
            "label": '证据分类输出上限',
        },
    )
    """人物画像证据分类最大输出 token 数"""


class AMemorixMemoryEvolutionConfig(ConfigBase):
    """A_Memorix 记忆演化配置"""

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用记忆演化',
        },
    )
    """是否启用记忆演化"""

    half_life_hours: float = Field(
        default=24.0,
        ge=0.1,
        json_schema_extra={
            "label": '半衰期',
        },
    )
    """半衰期小时数"""

    prune_threshold: float = Field(
        default=0.1,
        gt=0.0,
        lt=1.0,
        json_schema_extra={
            "label": '裁剪阈值',
        },
    )
    """裁剪阈值"""

    freeze_duration_hours: float = Field(
        default=24.0,
        ge=0.0,
        json_schema_extra={
            "label": '冻结时长',
        },
    )
    """冻结时长小时数"""

    revive_threshold: float = Field(
        default=0.15,
        gt=0.0,
        le=1.0,
        json_schema_extra={
            "label": '恢复阈值',
        },
    )
    """冻结关系恢复为活跃状态的保留强度阈值"""

    access_reinforcement_alpha: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "label": '访问加强系数',
        },
    )
    """记忆被最终采用时的饱和加强系数"""

    access_reinforcement_cooldown_minutes: float = Field(
        default=60.0,
        ge=0.0,
        json_schema_extra={
            "label": '访问加强冷却时间',
        },
    )
    """同一关系两次访问加强之间的最短分钟数，0表示不限制"""

    explicit_reinforcement_alpha: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "label": '显式加强系数',
        },
    )
    """用户显式加强或独立新证据的饱和加强系数"""

    weaken_alpha: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        json_schema_extra={
            "label": '弱化系数',
        },
    )
    """显式弱化事件的比例系数"""

    lifecycle_batch_size: int = Field(
        default=1000,
        ge=1,
        json_schema_extra={
            "label": '生命周期批量',
        },
    )
    """单轮处理的到期关系数量"""

    def model_post_init(self, context: Optional[dict] = None) -> None:
        if self.revive_threshold <= self.prune_threshold:
            raise ValueError("revive_threshold 必须大于 prune_threshold")
        return super().model_post_init(context)


class AMemorixAdvancedConfig(ConfigBase):
    """A_Memorix 高级运行时配置"""

    enable_auto_save: bool = Field(
        default=True,
        json_schema_extra={
            "label": '自动保存',
        },
    )
    """是否启用自动保存"""

    auto_save_interval_minutes: int = Field(
        default=5,
        ge=1,
        json_schema_extra={
            "label": '自动保存间隔',
        },
    )
    """自动保存间隔"""

    debug: bool = Field(
        default=False,
        json_schema_extra={
            "label": '调试模式',
        },
    )
    """是否启用调试"""


class AMemorixWebImportTimeoutConfig(ConfigBase):
    """A_Memorix 导入中心超时配置"""

    llm_call_seconds: float = Field(
        default=240.0,
        ge=0.0,
        json_schema_extra={
            "label": 'LLM 单次调用超时',
        },
    )
    """Web 导入中单次 LLM 抽取调用的超时时间，0 表示不额外限制"""

    process_poll_seconds: float = Field(
        default=1.0,
        ge=0.1,
        json_schema_extra={
            "label": '子进程轮询等待',
        },
    )
    """迁移或转换子进程状态轮询等待时间"""

    process_terminate_seconds: float = Field(
        default=5.0,
        ge=0.1,
        json_schema_extra={
            "label": '子进程终止等待',
        },
    )
    """取消任务时等待子进程正常终止的时间"""

    process_kill_seconds: float = Field(
        default=3.0,
        ge=0.1,
        json_schema_extra={
            "label": '子进程强杀等待',
        },
    )
    """取消任务时强制结束子进程后的等待时间"""

    convert_preflight_seconds: float = Field(
        default=20.0,
        ge=0.1,
        json_schema_extra={
            "label": '转换预检超时',
        },
    )
    """LPMM 转换依赖预检的超时时间"""


class AMemorixWebImportConfig(ConfigBase):
    """A_Memorix 导入中心配置"""

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用导入中心',
        },
    )
    """是否启用导入中心"""

    max_queue_size: int = Field(
        default=20,
        ge=1,
        json_schema_extra={
            "label": '最大队列',
        },
    )
    """最大队列长度"""

    max_files_per_task: int = Field(
        default=200,
        ge=1,
        json_schema_extra={
            "label": '单任务文件上限',
        },
    )
    """单任务最大文件数"""

    max_file_size_mb: int = Field(
        default=20,
        ge=1,
        json_schema_extra={
            "label": '单文件大小上限',
        },
    )
    """单文件大小上限 MB"""

    max_paste_chars: int = Field(
        default=200000,
        ge=100,
        json_schema_extra={
            "label": '粘贴字符上限',
        },
    )
    """粘贴字符数上限"""

    default_file_concurrency: int = Field(
        default=2,
        ge=1,
        json_schema_extra={
            "label": '默认文件并发',
        },
    )
    """默认文件并发"""

    default_chunk_concurrency: int = Field(
        default=4,
        ge=1,
        json_schema_extra={
            "label": '默认分块并发',
        },
    )
    """默认分块并发"""

    default_narrative_window_size: int = Field(
        default=1600,
        ge=200,
        json_schema_extra={
            "label": '默认叙事抽取窗口',
            "advanced": True,
        },
    )
    """默认叙事抽取窗口字符数"""

    default_narrative_overlap: int = Field(
        default=400,
        ge=0,
        json_schema_extra={
            "label": '默认叙事重叠字符',
            "advanced": True,
        },
    )
    """默认叙事窗口重叠字符数"""

    default_factual_target_size: int = Field(
        default=1200,
        ge=200,
        json_schema_extra={
            "label": '默认事实分块目标',
            "advanced": True,
        },
    )
    """默认事实分块目标字符数"""

    max_chunk_chars: int = Field(
        default=3200,
        ge=200,
        json_schema_extra={
            "label": '分块字符上限',
            "advanced": True,
        },
    )
    """单个抽取分块的字符上限"""

    timeout: AMemorixWebImportTimeoutConfig = Field(
        default_factory=AMemorixWebImportTimeoutConfig,
        json_schema_extra={
            "label": '导入超时',
        },
    )
    """导入中心超时配置"""


class AMemorixWebTuningConfig(ConfigBase):
    """A_Memorix 调优中心配置"""

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用调优中心',
        },
    )
    """是否启用调优中心"""

    max_queue_size: int = Field(
        default=8,
        ge=1,
        json_schema_extra={
            "label": '最大队列',
        },
    )
    """最大队列长度"""

    poll_interval_ms: int = Field(
        default=1200,
        ge=200,
        json_schema_extra={
            "label": '轮询间隔',
        },
    )
    """轮询间隔毫秒数"""

    default_intensity: Literal["quick", "standard", "deep"] = Field(
        default="standard",
        json_schema_extra={
            "label": '默认强度',
        },
    )
    """默认调优强度"""

    default_objective: Literal["precision_priority", "balanced", "recall_priority"] = Field(
        default="precision_priority",
        json_schema_extra={
            "label": '默认目标',
        },
    )
    """默认调优目标"""

    default_top_k_eval: int = Field(
        default=20,
        ge=1,
        json_schema_extra={
            "label": '默认评估 Top-K',
        },
    )
    """默认评估 Top-K"""

    default_sample_size: int = Field(
        default=24,
        ge=1,
        json_schema_extra={
            "label": '默认样本数',
        },
    )
    """默认样本数"""


class AMemorixWebConfig(ConfigBase):
    """A_Memorix Web 运维配置"""

    import_config: AMemorixWebImportConfig = Field(
        default_factory=AMemorixWebImportConfig,
        json_schema_extra={
            "label": '导入中心',
        },
    )
    """导入中心配置"""

    tuning: AMemorixWebTuningConfig = Field(
        default_factory=AMemorixWebTuningConfig,
        json_schema_extra={
            "label": '调优中心',
        },
    )
    """调优中心配置"""


class AMemorixConfig(ConfigBase):
    """长期记忆配置"""

    __ui_label__ = "记忆"
    __ui_order__ = 50

    plugin: AMemorixPluginConfig = Field(
        default_factory=AMemorixPluginConfig,
        json_schema_extra={
            "label": '记忆系统',
        },
    )
    """长期记忆系统的总开关"""

    integration: AMemorixIntegrationConfig = Field(
        default_factory=AMemorixIntegrationConfig,
        json_schema_extra={
            "label": '聊天中使用记忆',
        },
    )
    """控制麦麦在聊天中如何使用长期记忆"""

    storage: AMemorixStorageConfig = Field(
        default_factory=AMemorixStorageConfig,
        json_schema_extra={
            "label": '存储',
        },
    )
    """存储位置"""

    image_memory: AMemorixImageMemoryConfig = Field(
        default_factory=AMemorixImageMemoryConfig,
        json_schema_extra={
            "label": '图片记忆',
            "x-collapsed-by-default": True,
        },
    )
    """图片资产留存、图片嵌入和相似内容召回配置"""

    embedding: AMemorixEmbeddingConfig = Field(
        default_factory=AMemorixEmbeddingConfig,
        json_schema_extra={
            "label": '记忆向量化',
            "x-collapsed-by-default": True,
        },
    )
    """把记忆内容转换为向量时使用的基础设置"""

    retrieval: AMemorixRetrievalConfig = Field(
        default_factory=AMemorixRetrievalConfig,
        json_schema_extra={
            "label": '检索',
        },
    )
    """检索配置"""

    threshold: AMemorixThresholdConfig = Field(
        default_factory=AMemorixThresholdConfig,
        json_schema_extra={
            "label": '阈值',
        },
    )
    """阈值过滤配置"""

    filter: AMemorixFilterConfig = Field(
        default_factory=AMemorixFilterConfig,
        json_schema_extra={
            "label": '过滤',
        },
    )
    """聊天过滤配置"""

    global_memory_sharing_enabled: bool = Field(
        default=False,
        json_schema_extra={
            "label": '全局共享记忆',
            "x-widget": "switch",
        },
    )
    """是否让普通记忆查询在所有聊天流范围内检索"""

    shared_memory_groups: list[ChatStreamGroup] = Field(
        default_factory=list,
        json_schema_extra={
            "label": '共享记忆组',
            "x-widget": "custom",
            "x-display-as-section": True,
        },
    )
    """把需要互相参考长期记忆的群聊或私聊放到同一组"""

    episode: AMemorixEpisodeConfig = Field(
        default_factory=AMemorixEpisodeConfig,
        json_schema_extra={
            "label": 'Episode',
        },
    )
    """Episode 配置"""

    person_profile: AMemorixPersonProfileConfig = Field(
        default_factory=AMemorixPersonProfileConfig,
        json_schema_extra={
            "label": '人物画像',
        },
    )
    """人物画像配置"""

    memory: AMemorixMemoryEvolutionConfig = Field(
        default_factory=AMemorixMemoryEvolutionConfig,
        json_schema_extra={
            "label": '记忆演化',
        },
    )
    """记忆演化配置"""

    advanced: AMemorixAdvancedConfig = Field(
        default_factory=AMemorixAdvancedConfig,
        json_schema_extra={
            "label": '高级',
        },
    )
    """高级运行时配置"""

    web: AMemorixWebConfig = Field(
        default_factory=AMemorixWebConfig,
        json_schema_extra={
            "label": 'Web 运维',
        },
    )
    """Web 运维配置"""


class LearningItem(ConfigBase):
    platform: str = Field(
        default="",
        json_schema_extra={
            "label": '平台',
            "x-widget": "input",
        },
    )
    """平台，与ID一起留空表示全局"""

    item_id: str = Field(
        default="",
        json_schema_extra={
            "label": '聊天流 ID',
            "x-widget": "input",
        },
    )
    """要单独配置的群号或用户 ID；留空表示默认规则。"""

    type: Literal["group", "private"] = Field(
        default="group",
        json_schema_extra={
            "label": '聊天类型',
            "x-widget": "select",
            "x-option-descriptions": RULE_TYPE_OPTION_DESCRIPTIONS,
        },
    )
    """这条规则作用于群聊还是私聊。"""

    use: bool = Field(
        default=True,
        json_schema_extra={
            "label": '使用',
            "x-widget": "switch",
        },
    )
    """是否在这个聊天里使用已学到的内容。"""

    learn: bool = Field(
        default=True,
        json_schema_extra={
            "label": '学习',
            "x-widget": "switch",
        },
    )
    """是否从这个聊天里继续学习新内容。"""


ExperimentalConfig.model_rebuild()


class LearningBlacklistUser(ConfigBase):
    """按平台和用户 ID 精确匹配学习来源，不影响正常聊天。"""

    platform: str = Field(min_length=1, pattern=r"^\S+$", json_schema_extra={"label": "平台"})
    user_id: str = Field(min_length=1, pattern=r"^\S+$", json_schema_extra={"label": "用户 ID"})


class ExpressionConfig(ConfigBase):
    """表达配置类"""

    __ui_label__ = "学习"
    __ui_order__ = 40
    __ui_use_subtabs__ = True
    __ui_sub_label__ = "表达"

    expression_checked_only: bool = Field(
        default=False,
        json_schema_extra={
            "label": '仅使用精选表达',
            "x-widget": "switch",
            "x-row": "expression-learning-switches",
        },
    )
    """仅使用人工精选的表达。"""

    expression_self_reflect: bool = Field(
        default=True,
        json_schema_extra={
            "label": '优化表达方式学习',
            "x-widget": "switch",
            "x-row": "expression-learning-switches",
        },
    )
    """写入表达方式前先让 AI 检查，减少学到奇怪内容。"""

    use_vector_expression: bool = Field(
        default=False,
        json_schema_extra={
            "label": '表达选择',
            "x-widget": "discrete-slider",
            "options": ["false", "true"],
            "x-option-labels": {"false": "快速", "true": "精细"},
            "x-option-descriptions": {
                "false": "默认档位。加权随机抽取表达，直接供回复参考，不额外调用选择模型。",
                "true": "使用向量召回，再由 LLM 按语境筛选，需要配置嵌入模型。",
            },
            "advanced": False,
        },
    )
    """表达选择档位：false 为快速，加权随机抽样后直接注入，不额外调用选择 LLM；true 为精细，使用表达意图与嵌入召回，再由 LLM 筛选，需要配置嵌入模型。复古回复不使用表达选择。"""

    expression_vector_index_path: str = Field(
        default="data/expression_selection/expression_vector_index.json",
        json_schema_extra={
            "label": '表达向量索引路径',
            "x-widget": "input",
            "advanced": True,
        },
    )
    """向量召回使用的表达索引 JSON；相对路径按项目根目录解析。"""

    expression_vector_candidate_pool_size: int = Field(
        default=50,
        ge=1,
        le=50,
        json_schema_extra={
            "label": '向量候选上限',
            "x-widget": "input",
            "advanced": True,
        },
    )
    """向量召回后最多交给表达方式 LLM 选择的候选数；硬上限为 50。"""

    max_expression_learner: int = Field(
        default=3,
        json_schema_extra={
            "label": '表达学习最大并发',
            "x-widget": "input",
            "advanced": True,
        },
    )
    """同时运行的表达学习任务数量；太高可能占用更多资源。"""

    learning_list: list[LearningItem] = Field(
        default_factory=lambda: [
            LearningItem(
                platform="",
                item_id="",
                type="group",
                use=True,
                learn=True,
            )
        ],
        json_schema_extra={
            "label": '学习配置',
            "x-widget": "custom",
        },
    )
    """配置哪些聊天会学习和使用表达方式；默认规则不够时再单独添加。"""

    expression_groups: list[ChatStreamGroup] = Field(
        default_factory=list,
        json_schema_extra={
            "label": '共享共享组',
            "x-widget": "custom",
        },
    )
    """_wrap_让多个群聊或私聊共享学到的表达方式。"""

    learning_blacklist: List[LearningBlacklistUser] = Field(
        default_factory=list,
        json_schema_extra={"label": "学习黑名单", "x-widget": "custom"},
    )
    """不学习来源指向这些用户消息的表达；按平台和用户 ID 精确匹配，仍保留聊天上下文。"""


class JargonConfig(ConfigBase):
    """黑话配置类"""

    __ui_parent__ = "expression"
    __ui_label__ = "黑话"
    __ui_sub_label__ = "黑话"

    learning_list: list[LearningItem] = Field(
        default_factory=lambda: [
            LearningItem(
                platform="",
                item_id="",
                type="group",
                use=True,
                learn=True,
            )
        ],
        json_schema_extra={
            "label": '学习配置',
            "x-widget": "custom",
        },
    )
    """_wrap_配置哪些聊天会学习和使用黑话；默认规则不够时再单独添加。"""

    jargon_groups: list[ChatStreamGroup] = Field(
        default_factory=list,
        json_schema_extra={
            "label": '黑话共享组',
            "x-widget": "custom",
        },
    )
    """_wrap_让多个群聊或私聊共享学到的黑话。"""

    learning_blacklist: List[LearningBlacklistUser] = Field(
        default_factory=list,
        json_schema_extra={"label": "学习黑名单", "x-widget": "custom"},
    )
    """不学习原消息指向这些用户的黑话；按平台和用户 ID 精确匹配，仍保留聊天上下文。"""


class VoiceConfig(ConfigBase):
    """语音识别配置类"""

    __ui_parent__ = "message_receive"
    __ui_label__ = "语音"
    __ui_advanced__ = True

    enable_asr: bool = Field(
        default=False,
        json_schema_extra={
            "x-widget": "switch",
        },
    )
    """开启后麦麦可以把语音消息识别成文字再处理。"""


class EmojiCacheCleanupConfig(ConfigBase):
    """表情包缓存自动清理配置。"""

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "x-widget": "switch",
            "label": '启用表情包缓存自动清理',
        },
    )
    """开启后会自动删除长期未注册、未使用的表情包缓存。"""

    check_interval_hours: float = Field(
        default=6.0,
        ge=1.0 / 60.0,
        json_schema_extra={
            "x-widget": "input",
            "label": '表情包清理检查间隔（小时）',
        },
    )
    """每隔多少小时检查一次旧表情包缓存。"""

    emoji_file_retention_days: int = Field(
        default=30,
        ge=1,
        json_schema_extra={
            "x-widget": "input",
            "label": '未注册表情包文件保留天数',
        },
    )
    """未注册表情包文件多久没被使用后可以删除；已注册表情包永远不会由该任务删除。"""

    no_file_record_retention_days: int = Field(
        default=30,
        ge=1,
        json_schema_extra={
            "x-widget": "input",
            "label": '未注册表情包无文件记录保留天数',
        },
    )
    """未注册表情包文件删掉后，描述缓存记录还能保留多久。"""


class EmojiConfig(ConfigBase):
    """表情包配置类"""

    __ui_parent__ = "expression"
    __ui_label__ = "表情包"
    __ui_sub_label__ = "表情包"

    use_new_send_logic: bool = Field(
        default=False,
        json_schema_extra={
            "label": '采用新表情包发送逻辑',
            "x-widget": "switch",
        },
    )
    """开启后由思考模型直接查看并挑选表情包，在文字回复后发送，需要思考模型支持视觉；关闭时沿用独立选择并发送表情包的旧方式。"""

    emoji_send_num: int = Field(
        default=25,
        ge=1,
        le=64,
        json_schema_extra={
            "label": '单次发送候选数',
            "x-widget": "input",
            "advanced": True,
        },
    )
    """每次从多少个候选表情里挑一个发送；不是一次发送这么多。"""

    max_reg_num: int = Field(
        default=64,
        json_schema_extra={
            "label": '最大注册数量',
            "x-widget": "input",
        },
    )
    """最多保存多少个可用表情。"""

    do_replace: bool = Field(
        default=True,
        json_schema_extra={
            "label": '满额后替换旧表情',
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """表情满了以后是否用新表情替换旧表情。"""

    check_interval: int = Field(
        default=10,
        json_schema_extra={
            "label": '检查间隔',
            "x-widget": "input",
        },
    )
    """每隔多少分钟检查一次表情库状态。"""

    steal_emoji: bool = Field(
        default=True,
        json_schema_extra={
            "label": '收集聊天表情',
            "x-widget": "switch",
        },
    )
    """是否从聊天中自动收集别人发的表情。"""

    max_emoji_size_mb: float = Field(
        default=5.0,
        ge=0.0,
        json_schema_extra={
            "label": '收集表情大小上限（MB）',
            "x-widget": "input",
            "advanced": True,
        },
    )
    """收集表情时允许的最大文件大小；0 表示不限。"""

    content_filtration: bool = Field(
        default=False,
        json_schema_extra={
            "label": '启用内容过滤',
            "advanced": True,
            "x-widget": "switch",
        },
    )
    """开启后只保存内容合适的表情。"""

    collect_images: bool = Field(
        default=False,
        json_schema_extra={
            "label": '自动收图到额外图库',
            "x-widget": "switch",
        },
    )
    """开启后收集私聊图片和表情；群聊遵守收图名单。每条消息最多 24 张，单张不超过 16 MB。"""

    image_collection_mode: Literal["whitelist", "blacklist"] = Field(
        default="whitelist",
        json_schema_extra={
            "label": '群聊收图名单模式',
        },
    )
    """白名单只收列表中的群，黑名单收列表以外的群；不影响私聊。"""

    image_collection_groups: List[str] = Field(
        default_factory=list,
        json_schema_extra={
            "label": '收图群号列表',
        },
    )
    """逐项填写群号；空白名单不收群图，空黑名单收所有群图。"""

    cache_cleanup: EmojiCacheCleanupConfig = Field(default_factory=EmojiCacheCleanupConfig)
    """定期清理未注册表情包缓存，减少磁盘占用；已注册表情包不会被清理。"""


class KeywordRuleConfig(ConfigBase):
    """关键词规则配置类"""

    keywords: list[str] = Field(
        default_factory=lambda: [],
        json_schema_extra={
            "label": '关键词',
            "x-widget": "custom",
        },
    )
    """要匹配的关键词；命中任意一个即可触发。"""

    regex: list[str] = Field(
        default_factory=lambda: [],
        json_schema_extra={
            "label": '正则表达式',
            "x-widget": "custom",
        },
    )
    """要匹配的正则表达式；适合复杂文本规则。"""

    reaction: str = Field(
        default="",
        json_schema_extra={
            "label": '反应提示',
            "x-widget": "textarea",
        },
    )
    """命中后给麦麦看的提示内容，不会直接当作消息发送。"""

    def model_post_init(self, context: Optional[dict] = None) -> None:
        """验证配置"""
        if not self.keywords and not self.regex:
            raise ValueError("关键词规则必须至少包含keywords或regex中的一个")

        if not self.reaction:
            raise ValueError("关键词规则必须包含reaction")

        for pattern in self.regex:
            try:
                re.compile(pattern)
            except re.error as e:
                raise ValueError(f"无效的正则表达式 '{pattern}': {str(e)}") from e
        return super().model_post_init(context)


class KeywordReactionConfig(ConfigBase):
    """关键词配置类"""

    __ui_parent__ = "message_receive"

    keyword_rules: list[KeywordRuleConfig] = Field(
        default_factory=lambda: [],
        json_schema_extra={
            "label": '关键词规则',
            "x-widget": "custom",
        },
    )
    """命中关键词后，给麦麦追加一段固定反应提示。"""

    regex_rules: list[KeywordRuleConfig] = Field(
        default_factory=lambda: [],
        json_schema_extra={
            "label": '正则规则',
            "x-widget": "custom",
        },
    )
    """命中正则规则后，给麦麦追加一段固定反应提示。"""

    def model_post_init(self, context: Optional[dict] = None) -> None:
        """验证配置"""
        for rule in self.keyword_rules + self.regex_rules:
            if not isinstance(rule, KeywordRuleConfig):
                raise ValueError(f"规则必须是KeywordRuleConfig类型，而不是{type(rule).__name__}")
        return super().model_post_init(context)


class ResponsePostProcessConfig(ConfigBase):
    """回复后处理配置类"""

    __ui_label__ = "后处理"
    __ui_advanced__ = True
    __ui_order__ = 100

    enable_response_post_process: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用回复后处理',
            "x-widget": "switch",
        },
    )
    """开启后会对回复做错别字、分段等后处理。"""

    remove_bracket_content: bool = Field(
        default=True,
        json_schema_extra={
            "label": "清理括号内容",
            "x-widget": "switch",
        },
    )
    """规则后处理时去除回复中括号内的中文内容；关闭后保留，颜文字不受影响。"""

    typing_speed: float = Field(
        default=1.0,
        ge=0,
        le=2,
        json_schema_extra={
            "label": '打字速度',
            "x-widget": "slider",
            "x-row": "reply-speed",
            "step": 0.1,
            "advanced": True,
        },
    )
    """模拟打字等待时间；0 最快，1 默认，2 更慢。"""


class ChineseTypoConfig(ConfigBase):
    """中文错别字配置类"""

    __ui_parent__ = "response_post_process"

    enable: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用错别字',
            "x-widget": "switch",
        },
    )
    """让麦麦偶尔打错字，更像真人聊天。"""

    enable_correction_quote: bool = Field(
        default=True,
        json_schema_extra={
            "label": '错别字纠正时引用原消息',
            "x-widget": "switch",
            "x-row": "typo-correction-quote",
        },
    )
    """纠正错别字时，是否引用上一条包含错别字的消息。"""

    correction_quote_probability: float = Field(
        default=1.0,
        ge=0,
        le=1,
        json_schema_extra={
            "label": '错别字纠正引用概率',
            "x-widget": "slider",
            "x-row": "typo-correction-quote",
            "step": 0.01,
            "advanced": True,
        },
    )
    """生成纠正消息时，引用上一条错别字消息的概率。"""

    error_rate: float = Field(
        default=0.01,
        ge=0,
        le=1,
        json_schema_extra={
            "label": '单字错字概率',
            "x-widget": "slider",
            "step": 0.01,
            "advanced": True,
        },
    )
    """单个字被替换成错字的概率。"""

    min_freq: int = Field(
        default=9,
        json_schema_extra={
            "label": '最小字频',
            "x-widget": "input",
            "advanced": True,
        },
    )
    """只对常见程度达到该值的字尝试制造错字。"""

    tone_error_rate: float = Field(
        default=0.1,
        ge=0,
        le=1,
        json_schema_extra={
            "label": '声调错字概率',
            "x-widget": "slider",
            "step": 0.1,
            "advanced": True,
        },
    )
    """按相近声调制造错字的概率。"""

    word_replace_rate: float = Field(
        default=0.006,
        ge=0,
        le=1,
        json_schema_extra={
            "label": '整词替换概率',
            "x-widget": "slider",
            "step": 0.001,
            "advanced": True,
        },
    )
    """整词被替换成错词的概率。"""


class ResponseSplitterConfig(ConfigBase):
    """回复分割器配置类"""

    __ui_parent__ = "response_post_process"

    mode: Literal["rule", "llm"] = Field(
        default="rule",
        json_schema_extra={
            "label": '断句模式',
            "x-widget": "select",
            "options": ["rule", "llm"],
        },
    )
    """规则断句或使用 LLM 按语义断句。"""

    enable: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用回复分割',
            "x-widget": "switch",
        },
    )
    """把过长回复拆成多条发送。"""

    max_length: int = Field(
        default=512,
        json_schema_extra={
            "label": '单条最大长度',
            "x-widget": "input",
        },
    )
    """单条回复允许的最大长度。"""

    max_sentence_num: int = Field(
        default=8,
        json_schema_extra={
            "label": '单条最大句数',
            "x-widget": "input",
        },
    )
    """单条回复最多包含多少个句子。"""

    max_split_num: int = Field(
        default=3,
        ge=1,
        json_schema_extra={
            "label": '最多分割条数',
            "x-widget": "input",
        },
    )
    """一次回复最多拆成几条消息。"""

    enable_kaomoji_protection: bool = Field(
        default=False,
        json_schema_extra={
            "label": '保护颜文字',
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """尽量避免把颜文字从中间拆开。"""

    enable_overflow_return_all: bool = Field(
        default=False,
        json_schema_extra={
            "label": '超限保留全文',
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """句子太多时是否直接保留完整回复，不再强行截断。"""


class LogConfig(ConfigBase):
    """日志配置类"""

    __ui_label__ = "调试"
    __ui_advanced__ = True
    __ui_order__ = 130

    date_style: str = Field(
        default="m-d H:i:s",
        json_schema_extra={
            "label": '日期格式',
            "x-widget": "input",
        },
    )
    """日志时间的显示格式。"""

    log_level_style: Literal["lite", "compact", "full"] = Field(
        default="lite",
        json_schema_extra={
            "label": '日志等级样式',
            "x-widget": "select",
        },
    )
    """日志等级的显示样式，只影响日志外观。"""

    color_text: Literal["none", "title", "full"] = Field(
        default="full",
        json_schema_extra={
            "label": '控制台颜色',
            "x-widget": "select",
        },
    )
    """控制台日志颜色范围。"""

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        json_schema_extra={
            "label": '全局日志级别',
            "x-widget": "select",
        },
    )
    """全局最低日志等级；DEBUG 最详细，ERROR 最安静。"""

    console_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        json_schema_extra={
            "label": '控制台日志级别',
            "x-widget": "select",
        },
    )
    """控制台输出的最低日志等级。"""

    file_log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="DEBUG",
        json_schema_extra={
            "label": '文件日志级别',
            "x-widget": "select",
        },
    )
    """写入日志文件的最低日志等级。"""

    log_file_max_bytes: int = Field(
        default=5 * 1024 * 1024,
        json_schema_extra={
            "label": '单个日志大小',
            "x-widget": "input",
        },
    )
    """单个日志文件超过这个大小后会轮转。"""

    max_log_files: int = Field(
        default=30,
        json_schema_extra={
            "label": '日志文件保留数',
            "x-widget": "input",
        },
    )
    """最多保留多少个主日志文件。"""

    log_cleanup_days: int = Field(
        default=30,
        json_schema_extra={
            "label": '日志保留天数',
            "x-widget": "input",
        },
    )
    """主日志文件超过多少天后清理。"""

    llm_request_snapshot_limit: int = Field(
        default=128,
        json_schema_extra={
            "label": '请求快照保留数',
            "x-widget": "input",
        },
    )
    """失败模型请求快照最多保留多少份。"""

    maisaka_prompt_preview_limit: int = Field(
        default=256,
        json_schema_extra={
            "label": 'Prompt 预览保留数',
            "x-widget": "input",
        },
    )
    """每个聊天最多保留多少组 Prompt 预览。"""


    memory_diagnostics_enabled: bool = Field(default=True)
    """启用独立内存诊断日志；最多四个 5 MiB 文件，修改后重启生效。"""

    memory_diagnostics_deep_enabled: bool = Field(default=False)
    """启用 tracemalloc 分配位置对比（每十分钟）；有额外内存和 CPU 开销，排查时开启，重启生效。"""

    memory_diagnostics_interval_seconds: float = Field(default=60.0, ge=10.0)
    """轻量内存诊断采集间隔（秒，至少 10 秒），修改后重启生效。"""

    event_loop_watchdog_enabled: bool = Field(
        default=False,
        json_schema_extra={
            "label": '事件循环卡顿看门狗',
            "x-widget": "switch",
        },
    )
    """是否记录事件循环卡顿；主循环与 WebUI 循环各有一份，用于排查界面卡顿。"""

    event_loop_watchdog_warn_seconds: float = Field(
        default=0.5,
        json_schema_extra={
            "label": '卡顿告警阈值（秒）',
            "x-widget": "input",
        },
    )
    """事件循环唤醒延迟超过该秒数时记录一条警告日志。"""

    suppress_libraries: list[str] = Field(
        default_factory=lambda: [
            "faiss",
            "httpx",
            "httpx2",
            "urllib3",
            "asyncio",
            "websockets",
            "httpcore",
            "httpcore2",
            "requests",
            "sqlalchemy",
            "openai",
            "uvicorn",
            "jieba",
        ],
        json_schema_extra={
            "label": '屏蔽库日志',
            "x-widget": "custom",
            "advanced": True,
        },
    )
    """完全不显示日志的第三方库名称列表。"""

    library_log_levels: dict[str, str] = Field(
        default_factory=lambda: {"aiohttp": "WARNING", "PIL": "WARNING"},
        json_schema_extra={
            "label": '库日志级别',
            "x-widget": "custom",
            "advanced": True,
        },
    )
    """单独设置某些第三方库的日志等级。"""


class TelemetryConfig(ConfigBase):
    """遥测配置类"""

    __ui_parent__ = "debug"

    enable: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用遥测',
            "x-widget": "switch",
        },
    )
    """是否发送匿名运行统计；关闭不影响正常使用。"""


class DebugConfig(ConfigBase):
    """调试配置类"""

    __ui_parent__ = "log"
    __ui_label__ = "其他"

    replyer_retro_prompt: bool = Field(
        default=False,
        json_schema_extra={
            "label": '复古回复提示词',
            "x-widget": "switch",
        },
    )
    """按旧版（0.12.x）的方式组织 replyer 提示词：全部回复指令集中在一份完整模板里，用块占位符填充，群聊/私聊/简短回复各用一套模板，并整段作为一条 user 消息发送。仅检查实际分配给 replyer 的模型：名称或标识包含 mai_replier（兼容 mai-replier），或为 v2p1-contract、v2p1-raw 时自动开启且不可关闭；解除这些模型的 replyer 分配后清除自动开关，未分配的模型不影响此设置。其他模型可手动开启。"""

    enable_console_input: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用终端输入',
            "x-widget": "switch",
        },
    )
    """在交互式终端中启用本地消息和指令输入。"""

    show_maisaka_thinking: bool = Field(
        default=False,
        json_schema_extra={
            "label": '显示终端思考大框',
            "x-widget": "switch",
        },
    )
    """在终端显示思考过程大框，不影响推理记录保存和 WebUI 查看。"""

    save_maisaka_reasoning: bool = Field(
        default=True,
        json_schema_extra={
            "label": '保存推理记录',
            "x-widget": "switch",
        },
    )
    """保存 Planner、工具调用及聊天回想的完整推理记录，供 WebUI 查看，与终端显示独立。"""


    keep_prompt_preview_json_base64: bool = Field(
        default=False,
        json_schema_extra={
            "label": '保留预览图片数据',
            "x-widget": "switch",
        },
    )
    """Prompt 预览里保留图片 base64，便于复现但会占空间。"""

    record_tool_structured_content: bool = Field(
        default=False,
        json_schema_extra={
            "label": '记录工具结构化内容',
            "x-widget": "switch",
        },
    )
    """保存工具返回的结构化内容，便于调试但会增加数据库体积。"""

    enable_llm_cache_stats: bool = Field(
        default=False,
        json_schema_extra={
            "label": '记录模型缓存统计',
            "x-widget": "switch",
        },
    )
    """记录模型 prompt cache 统计，用于性能调试。"""

    force_plugin_compatibility: bool = Field(
        default=False,
        json_schema_extra={
            "label": '强制插件兼容',
            "x-widget": "switch",
        },
    )
    """跳过插件声明的 Host 和 SDK 版本范围校验，直接加载插件；开启后需重启生效。"""


class ExtraPromptItem(ConfigBase):
    platform: str = Field(
        default="",
        json_schema_extra={
            "x-widget": "input",
        },
    )
    """额外提示作用的平台，和聊天流 ID、提示内容需要一起填写。"""

    item_id: str = Field(
        default="",
        json_schema_extra={
            "x-widget": "input",
        },
    )
    """额外提示作用的群号或用户 ID。"""

    rule_type: Literal["group", "private"] = Field(
        default="group",
        json_schema_extra={
            "x-widget": "select",
            "x-option-descriptions": RULE_TYPE_OPTION_DESCRIPTIONS,
        },
    )
    """额外提示作用于群聊还是私聊。"""

    prompt: str = Field(
        default="",
        json_schema_extra={
            "x-widget": "textarea",
        },
    )
    """给这个聊天额外补充的要求。"""

    def model_post_init(self, context: Optional[dict] = None) -> None:
        if not self.platform and not self.item_id and not self.prompt:
            return super().model_post_init(context)
        if not self.platform or not self.item_id or not self.prompt:
            raise ValueError("ExtraPromptItem 中 platform, id 和 prompt 不能为空")
        return super().model_post_init(context)


class MaimMessageConfig(ConfigBase):
    """maim_message配置类"""

    __ui_parent__ = "debug"

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用 maim_message 服务',
            "x-widget": "switch",
        },
    )
    """消息服务总开关；关闭后不启动旧版 WS 和新版 API 服务，重启生效，不影响插件式适配器。"""

    ws_server_host: str = Field(
        default="127.0.0.1",
        json_schema_extra={
            "label": '旧版 WS 主机',
            "x-widget": "input",
        },
    )
    """旧版 WebSocket 服务监听地址；不清楚就保持默认。"""

    ws_server_port: int = Field(
        default=8000,
        json_schema_extra={
            "label": '旧版 WS 端口',
            "x-widget": "input",
        },
    )
    """旧版 WebSocket 服务端口。"""

    auth_token: list[str] = Field(
        default_factory=lambda: [],
        json_schema_extra={
            "label": '旧版认证令牌',
            "x-widget": "custom",
        },
    )
    """旧版 API 的认证令牌；为空表示不验证。"""

    enable_api_server: bool = Field(
        default=False,
        json_schema_extra={
            "label": '启用新版 API',
            "x-widget": "switch",
        },
    )
    """是否开启新版 API Server，供外部程序调用麦麦。"""

    api_server_host: str = Field(
        default="0.0.0.0",
        json_schema_extra={
            "label": '新版 API 主机',
            "x-widget": "input",
        },
    )
    """新版 API Server 监听地址；0.0.0.0 表示允许外部访问。"""

    api_server_port: int = Field(
        default=8090,
        json_schema_extra={
            "label": '新版 API 端口',
            "x-widget": "input",
        },
    )
    """新版 API Server 监听端口。"""

    api_server_use_wss: bool = Field(
        default=False,
        json_schema_extra={
            "label": '新版 API 使用 WSS',
            "x-widget": "switch",
        },
    )
    """新版 API Server 是否使用加密 WebSocket。"""

    api_server_cert_file: str = Field(
        default="",
        json_schema_extra={
            "label": 'WSS 证书文件',
            "x-widget": "input",
        },
    )
    """WSS 使用的证书文件路径。"""

    api_server_key_file: str = Field(
        default="",
        json_schema_extra={
            "label": 'WSS 私钥文件',
            "x-widget": "input",
        },
    )
    """WSS 使用的私钥文件路径。"""

    api_server_allowed_api_keys: list[str] = Field(
        default_factory=lambda: [],
        json_schema_extra={
            "label": '新版 API Key 白名单',
            "x-widget": "custom",
        },
    )
    """允许访问新版 API 的 Key 列表；为空表示不限制。"""


class WebUIConfig(ConfigBase):
    """WebUI配置类"""

    __ui_label__ = "WebUI"
    __ui_advanced__ = True
    __ui_order__ = 110

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用 WebUI',
            "x-widget": "switch",
        },
    )
    """是否加载 WebUI 管理界面和管理接口；关闭后公共 HTTP 文件传输仍然可用。"""

    mode: Literal["development", "production"] = Field(
        default="production",
        json_schema_extra={
            "label": '运行模式',
            "x-widget": "select",
        },
    )
    """WebUI 运行模式；普通使用保持 production。"""

    anti_crawler_mode: Literal["false", "strict", "loose", "basic"] = Field(
        default="basic",
        json_schema_extra={
            "label": '防爬虫模式',
            "x-widget": "select",
        },
    )
    """防爬虫策略；basic 只记录，strict/loose 会拦截更多请求。"""

    allowed_ips: str = Field(
        default="127.0.0.1",
        json_schema_extra={
            "label": '允许访问 IP',
            "x-widget": "comma-list",
            "x-placeholder": "127.0.0.1",
        },
    )
    """允许访问 WebUI 的 IP，多个用逗号分隔。"""

    trusted_proxies: str = Field(
        default="",
        json_schema_extra={
            "label": '可信代理 IP',
            "x-widget": "comma-list",
            "x-placeholder": "127.0.0.1",
        },
    )
    """可信反向代理 IP；只有这些代理传来的真实 IP 会被信任。"""

    trust_xff: bool = Field(
        default=False,
        json_schema_extra={
            "label": '信任 XFF',
            "x-widget": "switch",
        },
    )
    """是否信任 X-Forwarded-For 里的真实访客 IP。"""

    secure_cookie: bool = Field(
        default=False,
        json_schema_extra={
            "label": '安全 Cookie',
            "x-widget": "switch",
        },
    )
    """只在 HTTPS 下发送登录 Cookie；没有 HTTPS 时不要开启。"""

    enforce_public_outbound_url: bool = Field(
        default=True,
        json_schema_extra={
            "label": '强制公网出站 URL 校验',
            "x-widget": "switch",
            "advanced": False,
        },
    )
    """限制 WebUI 访问外部 URL，降低访问内网地址的风险。"""

class MCPAuthorizationConfig(ConfigBase):
    """MCP HTTP 认证配置。"""

    mode: Literal["none", "bearer"] = Field(
        default="none",
        json_schema_extra={
            "label": '认证方式',
            "x-widget": "select",
            "x-option-labels": {
                "none": "无认证",
                "bearer": "Bearer Token",
            },
        },
    )
    """MCP HTTP 认证方式；none 表示不认证。"""

    bearer_token: str = Field(
        default="",
        json_schema_extra={
            "label": 'Bearer Token',
            "x-widget": "password",
        },
    )
    """Bearer 认证令牌，只在 mode 为 bearer 时使用。"""

class MCPRootItemConfig(ConfigBase):
    """单个 MCP Root 配置。"""

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用 Root',
            "x-widget": "switch",
        },
    )
    """是否启用这个 Root。"""

    uri: str = Field(
        default="",
        json_schema_extra={
            "label": 'Root URI',
            "x-widget": "input",
        },
    )
    """Root 的 URI，文件夹一般写 file:/// 开头的路径。"""

    name: str = Field(
        default="",
        json_schema_extra={
            "label": '显示名称',
            "x-widget": "input",
        },
    )
    """这个 Root 在 MCP 里的显示名称。"""

    def model_post_init(self, context: Optional[dict] = None) -> None:
        """验证单个 Root 配置。

        Args:
            context: Pydantic 传入的上下文对象。

        Returns:
            None
        """

        if self.enabled and not self.uri.strip():
            raise ValueError("启用的 MCP Root 必须填写 uri")
        return super().model_post_init(context)


class MCPRootsConfig(ConfigBase):
    """MCP Roots 能力配置。"""

    enable: bool = Field(
        default=False,
        json_schema_extra={
            "label": '启用 Roots',
            "x-widget": "switch",
        },
    )
    """是否向 MCP 服务器暴露 Roots 能力。"""

    items: list[MCPRootItemConfig] = Field(
        default_factory=lambda: [],
        json_schema_extra={
            "label": 'Root 列表',
            "x-widget": "custom",
        },
    )
    """允许 MCP 服务器看到的目录或资源列表。"""


class MCPSamplingConfig(ConfigBase):
    """MCP Sampling 能力配置。"""

    enable: bool = Field(
        default=False,
        json_schema_extra={
            "label": '启用 Sampling',
            "x-widget": "switch",
        },
    )
    """是否声明支持 MCP Sampling。"""

    task_name: str = Field(
        default="planner",
        json_schema_extra={
            "label": '模型任务',
            "x-widget": "input",
        },
    )
    """MCP Sampling 调用模型时使用的任务名。"""

    tool_support: bool = Field(
        default=False,
        json_schema_extra={
            "label": '允许 Sampling 使用工具',
            "x-widget": "switch",
        },
    )
    """Sampling 过程中是否允许继续使用工具。"""


class MCPElicitationConfig(ConfigBase):
    """MCP Elicitation 能力配置。"""

    enable: bool = Field(
        default=False,
        json_schema_extra={
            "label": '启用 Elicitation（暂未支持）',
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """是否声明支持 MCP Elicitation。"""

    allow_form: bool = Field(
        default=True,
        json_schema_extra={
            "label": '允许表单请求',
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """是否允许 MCP 服务器请求填写表单。"""

    allow_url: bool = Field(
        default=False,
        json_schema_extra={
            "label": '允许 URL 请求',
            "x-widget": "switch",
            "advanced": True,
        },
    )
    """是否允许 MCP 服务器请求打开 URL。"""

    def model_post_init(self, context: Optional[dict] = None) -> None:
        """验证 Elicitation 配置。

        Args:
            context: Pydantic 传入的上下文对象。

        Returns:
            None
        """

        if self.enable and not (self.allow_form or self.allow_url):
            raise ValueError("启用 MCP Elicitation 时至少需要允许一种模式")
        return super().model_post_init(context)


class MCPClientConfig(ConfigBase):
    """MCP 客户端宿主能力配置。"""

    client_name: str = Field(
        default="MaiBot",
        json_schema_extra={
            "label": '客户端名称',
            "x-widget": "input",
            "advanced": True,
        },
    )
    """对 MCP 服务器展示的客户端名称。"""

    client_version: str = Field(
        default="1.0.0",
        json_schema_extra={
            "label": '客户端版本',
            "x-widget": "input",
            "advanced": True,
        },
    )
    """对 MCP 服务器展示的客户端版本。"""

    roots: MCPRootsConfig = Field(
        default_factory=MCPRootsConfig,
        json_schema_extra={"label": 'Roots 能力', "advanced": True},
    )
    """是否向 MCP 服务器提供可访问的文件根目录。"""

    sampling: MCPSamplingConfig = Field(
        default_factory=MCPSamplingConfig,
        json_schema_extra={"label": 'Sampling 能力', "advanced": True},
    )
    """是否允许 MCP 服务器请求麦麦调用模型。"""

    elicitation: MCPElicitationConfig = Field(
        default_factory=MCPElicitationConfig,
        json_schema_extra={"label": 'Elicitation 能力', "advanced": True},
    )
    """是否允许 MCP 服务器向麦麦请求补充信息。"""


class MCPServerItemConfig(ConfigBase):
    """单个 MCP 服务器配置。"""

    name: str = Field(
        default="",
        json_schema_extra={
            "label": '服务名称',
            "x-widget": "input",
        },
    )
    """MCP 服务器名称，必须唯一。"""

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用服务',
            "x-widget": "switch",
        },
    )
    """是否启用这个 MCP 服务器。"""

    transport: Literal["stdio", "streamable_http", "sse"] = Field(
        default="stdio",
        json_schema_extra={
            "label": '传输方式',
            "x-widget": "select",
            "x-option-labels": {
                "stdio": "本地命令（stdio）",
                "streamable_http": "远程 HTTP",
                "sse": "旧版 SSE",
            },
        },
    )
    """连接方式；本地命令通常用 stdio，远程服务用 HTTP/SSE。"""

    command: str = Field(
        default="",
        json_schema_extra={
            "label": '启动命令',
            "x-widget": "input",
        },
    )
    """stdio 模式下启动服务器的命令。"""

    args: list[str] = Field(
        default_factory=lambda: [],
        json_schema_extra={
            "label": '命令参数',
            "x-widget": "custom",
        },
    )
    """stdio 模式下传给命令的参数。"""

    env: dict[str, str] = Field(
        default_factory=lambda: {},
        json_schema_extra={
            "label": '环境变量',
            "x-widget": "custom",
        },
    )
    """stdio 模式下额外传入的环境变量。"""

    url: str = Field(
        default="",
        json_schema_extra={
            "label": '服务 URL',
            "x-widget": "input",
        },
    )
    """HTTP 或 SSE 模式下的服务器地址。"""

    headers: dict[str, str] = Field(
        default_factory=lambda: {},
        json_schema_extra={
            "label": '请求 Headers',
            "x-widget": "custom",
        },
    )
    """HTTP/SSE 请求时附加的请求头。"""

    http_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        json_schema_extra={
            "label": 'HTTP 请求超时',
            "x-widget": "number",
        },
    )
    """HTTP 请求多久没响应就算超时。"""

    read_timeout_seconds: float = Field(
        default=300.0,
        gt=0,
        json_schema_extra={
            "label": '会话读取超时',
            "x-widget": "number",
        },
    )
    """连接建立后，等服务器消息的最长时间。"""

    authorization: MCPAuthorizationConfig = Field(
        default_factory=MCPAuthorizationConfig,
        json_schema_extra={"label": '远程认证'},
    )
    """HTTP/SSE 连接的认证设置。"""

    def model_post_init(self, context: Optional[dict] = None) -> None:
        """验证 MCP 服务器配置。

        Args:
            context: Pydantic 传入的上下文对象。

        Returns:
            None
        """

        if not self.enabled:
            return super().model_post_init(context)

        if not self.name.strip():
            raise ValueError("MCPServerItemConfig.name 不能为空")

        if self.transport == "stdio" and not self.command.strip():
            raise ValueError(f"MCP 服务器 {self.name} 使用 stdio 时必须填写 command")

        if self.transport == "streamable_http" and not self.url.strip():
            raise ValueError(f"MCP 服务器 {self.name} 使用 streamable_http 时必须填写 url")

        if self.transport == "sse" and not self.url.strip():
            raise ValueError(f"MCP 服务器 {self.name} 使用 sse 时必须填写 url")

        if self.authorization.mode == "bearer" and not self.authorization.bearer_token.strip():
            raise ValueError(f"MCP 服务器 {self.name} 使用 bearer 认证时必须填写 bearer_token")

        return super().model_post_init(context)


class MCPConfig(ConfigBase):
    """MCP 总配置。"""

    __ui_parent__ = "maisaka"

    enable: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用 MCP',
            "x-widget": "switch",
        },
    )
    """是否启用 MCP 工具接入能力。"""

    client: MCPClientConfig = Field(
        default_factory=MCPClientConfig,
        json_schema_extra={"label": '客户端高级能力', "advanced": True},
    )
    """麦麦作为 MCP 客户端时声明的能力。"""

    servers: list[MCPServerItemConfig] = Field(
        default_factory=lambda: [],
        json_schema_extra={
            "label": 'MCP 服务',
            "x-widget": "custom",
        },
    )
    """_wrap_要连接的 MCP 服务器列表。"""

    def model_post_init(self, context: Optional[dict] = None) -> None:
        """验证 MCP 总配置。

        Args:
            context: Pydantic 传入的上下文对象。

        Returns:
            None
        """

        server_names = [server.name.strip() for server in self.servers if server.enabled and server.name.strip()]
        if len(server_names) != len(set(server_names)):
            raise ValueError("MCP 配置中的服务器名称不能重复")
        return super().model_post_init(context)


class CommandPermissionConfig(ConfigBase):
    """单个命令的额外放行规则。"""

    allow_users: list[str] = Field(default_factory=list)
    """允许执行命令的用户，格式如 qq:123456789。"""

    allow_chats: list[str] = Field(default_factory=list)
    """允许执行命令的真实聊天流 ID。"""


class PluginConfig(ConfigBase):
    """插件管理配置类"""

    __ui_label__ = "插件"
    __ui_advanced__ = True
    __ui_order__ = 120

    permission: list[str] = Field(
        default_factory=list,
        json_schema_extra={
            "label": '插件管理权限',
            "x-widget": "tags",
            "x-placeholder": "qq:123456789",
        },
    )
    """允许用聊天命令管理插件的用户，格式如 qq:123456789。"""

    silent_permission_denied: bool = Field(
        default=False,
        json_schema_extra={
            "label": '不显示无权限提示',
            "x-widget": "switch",
        },
    )
    """开启后，用户执行无权限命令时不再发送提示消息，仅静默拦截并记录日志。"""

    command_permissions: Dict[str, CommandPermissionConfig] = Field(
        default_factory=dict,
        json_schema_extra={"hidden": True},
    )
    """受保护命令按用户和真实聊天流配置的额外放行规则。"""

    disabled_commands: List[str] = Field(
        default_factory=list,
        json_schema_extra={"hidden": True},
    )
    """在命令管理中停用的命令 ID 列表（格式为 plugin_id.command_name，内置命令为 core.clear）。"""


class PluginRuntimeRenderConfig(ConfigBase):
    """插件运行时浏览器渲染配置。"""

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用浏览器渲染',
            "x-widget": "switch",
        },
    )
    """是否允许插件使用浏览器渲染能力。"""

    browser_ws_endpoint: str = Field(
        default="",
        json_schema_extra={
            "label": '浏览器调试地址',
            "x-widget": "input",
        },
    )
    """已有 Chrome/Chromium 的调试地址；留空则自动启动。"""

    executable_path: str = Field(
        default="",
        json_schema_extra={
            "label": '浏览器程序路径',
            "x-widget": "input",
        },
    )
    """浏览器程序路径；留空自动查找。"""

    browser_install_root: str = Field(
        default="data/playwright-browsers",
        json_schema_extra={
            "label": '浏览器安装目录',
            "x-widget": "input",
        },
    )
    """自动下载浏览器时保存的位置。"""

    headless: bool = Field(
        default=True,
        json_schema_extra={
            "label": '无界面运行',
            "x-widget": "switch",
        },
    )
    """是否隐藏浏览器窗口运行。"""

    launch_args: list[str] = Field(
        default_factory=lambda: [
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-setuid-sandbox",
            "--no-sandbox",
            "--no-zygote",
        ],
        json_schema_extra={
            "label": '启动参数',
            "x-widget": "custom",
        },
    )
    """启动浏览器时附加的命令参数。"""

    concurrency_limit: int = Field(
        default=2,
        ge=1,
        json_schema_extra={
            "label": '并发渲染数',
            "x-widget": "number",
        },
    )
    """同时最多运行多少个渲染任务。"""

    startup_timeout_sec: float = Field(
        default=20.0,
        gt=0,
        json_schema_extra={
            "label": '启动超时秒数',
            "x-widget": "number",
        },
    )
    """浏览器启动或连接的最长等待时间。"""

    render_timeout_sec: float = Field(
        default=15.0,
        gt=0,
        json_schema_extra={
            "label": '渲染超时秒数',
            "x-widget": "number",
        },
    )
    """单次渲染任务的最长等待时间。"""

    auto_download_chromium: bool = Field(
        default=True,
        json_schema_extra={
            "label": '自动下载 Chromium',
            "x-widget": "switch",
        },
    )
    """找不到浏览器时是否自动下载 Chromium。"""

    download_connection_timeout_sec: float = Field(
        default=120.0,
        gt=0,
        json_schema_extra={
            "label": '下载连接超时秒数',
            "x-widget": "number",
        },
    )
    """下载 Chromium 时的连接超时时间。"""

    restart_after_render_count: int = Field(
        default=200,
        ge=0,
        json_schema_extra={
            "label": '渲染后重启次数',
            "x-widget": "number",
        },
    )
    """渲染多少次后重启浏览器；0 表示不自动重启。"""


class PluginRuntimeConfig(ConfigBase):
    """插件运行时配置类"""

    __ui_parent__ = "plugin"
    __ui_label__ = "运行时"

    enabled: bool = Field(
        default=True,
        json_schema_extra={
            "label": '启用插件运行时',
            "x-widget": "switch",
        },
    )
    """是否启用新版插件运行时。"""

    health_check_interval_sec: float = Field(
        default=30.0,
        json_schema_extra={
            "label": '健康检查间隔秒数',
            "x-widget": "number",
        },
    )
    """每隔多少秒检查一次插件运行状态。"""

    max_restart_attempts: int = Field(
        default=3,
        json_schema_extra={
            "label": '最大重启次数',
            "x-widget": "number",
        },
    )
    """插件 Runner 崩溃后最多自动重启几次。"""

    runner_spawn_timeout_sec: float = Field(
        default=30.0,
        json_schema_extra={
            "label": 'Runner 启动超时秒数',
            "x-widget": "number",
        },
    )
    """等待插件 Runner 启动完成的最长时间。"""

    hook_blocking_timeout_sec: float = Field(
        default=60,
        json_schema_extra={
            "label": '阻塞 Hook 超时秒数',
            "x-widget": "number",
        },
    )
    """单个阻塞 Hook 最多允许运行多久。"""

    ipc_socket_path: str = Field(
        default="",
        json_schema_extra={
            "label": '通信 Socket 路径',
            "x-widget": "input",
        },
    )
    """
    自定义插件通信 Socket 路径；留空自动生成。
    """

    render: PluginRuntimeRenderConfig = Field(
        default_factory=PluginRuntimeRenderConfig,
        json_schema_extra={
            "label": '浏览器渲染',
        },
    )
    """插件需要网页截图或渲染时使用的浏览器配置。"""
