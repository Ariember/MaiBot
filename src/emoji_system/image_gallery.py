"""图库收集、标签与检索，共用主程序模型和消息组件。"""

from functools import lru_cache
from io import BytesIO
from itertools import islice
from typing import Any, Dict, Iterator, List, Optional, TYPE_CHECKING

from PIL import Image
from sqlmodel import select

import asyncio
import base64
import json
import sqlite3

from src.common.data_models.message_component_data_model import (
    EmojiComponent,
    ForwardComponent,
    ForwardNodeComponent,
    ImageComponent,
    StandardMessageComponents,
)
from src.common.llm_json import parse_llm_json
from src.common.database.database import get_db_session
from src.common.database.database_model import Images, ImageType
from src.common.logger import get_logger
from src.common.paths import get_instance_root
from src.common.utils.utils_image import ImageUtils
from src.config.config import global_config
from src.prompt.prompt_manager import prompt_manager
from src.services.llm_service import LLMServiceClient

from .emoji_manager import _is_vlm_task_configured
from .image_library import ImageLibrary, normalize_tags

if TYPE_CHECKING:
    from src.chat.message_receive.message import SessionMessage

logger = get_logger("image_gallery")
MAX_IMAGE_BYTES = 16 * 1024 * 1024


@lru_cache(maxsize=1)
def get_image_library() -> ImageLibrary:
    return ImageLibrary(get_instance_root() / "data" / "image_library", MAX_IMAGE_BYTES, 5000)


def iter_images(components: List[StandardMessageComponents]) -> Iterator[ImageComponent | EmojiComponent]:
    for component in components:
        if isinstance(component, (ImageComponent, EmojiComponent)):
            yield component
        elif isinstance(component, ForwardNodeComponent):
            for node in component.forward_components:
                yield from iter_images(node.content)
        elif isinstance(component, ForwardComponent):
            yield from iter_images(component.content)


async def collect_message_images(message: "SessionMessage") -> None:
    cfg = global_config.emoji
    if not cfg.collect_images:
        return
    group = message.message_info.group_info
    if group is not None:
        listed = str(group.group_id) in cfg.image_collection_groups
        if listed != (cfg.image_collection_mode == "whitelist"):
            return

    def collect() -> None:
        library = get_image_library()
        for component in islice(iter_images(message.raw_message.components), 24):
            if not component.binary_data:
                continue
            try:
                tags = ["表情包"] if isinstance(component, EmojiComponent) else []
                library.add_bytes(component.binary_data, "聊天图片", tags)
            except (ValueError, OSError, sqlite3.Error) as exc:
                logger.warning(f"图库收图失败: {exc}")

    try:
        await asyncio.to_thread(collect)
    except (OSError, sqlite3.Error) as exc:
        logger.warning(f"无法打开聊天图库: {exc}")


def _caption_image(library: ImageLibrary, image_id: str) -> str:
    with Image.open(BytesIO(library.read_bytes(image_id))) as image:
        # 标签分析使用首帧缩图，发送仍读取原始文件。
        image.thumbnail((1024, 1024))
        buffer = BytesIO()
        ImageUtils._prepare_image_for_receive_compression(image).save(buffer, "JPEG", quality=85)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


async def caption_library_image(image_id: str) -> None:
    library = await asyncio.to_thread(get_image_library)
    try:
        image = await asyncio.to_thread(_caption_image, library, image_id)
        prompt = await prompt_manager.render_prompt(prompt_manager.get_prompt("gallery_tags"))
        async with asyncio.timeout(60):
            result = await LLMServiceClient(
                task_name="vlm", request_type="emoji.gallery.tags"
            ).generate_response_for_image(
                prompt,
                image,
                "jpeg",
            )
        data = parse_llm_json(result.response)
        tags = normalize_tags(data.get("tags") if isinstance(data, dict) else data)[:7]
        if not tags:
            raise ValueError("图片模型未返回有效标签")
        await asyncio.to_thread(library.set_tags, image_id, tags, True)
    except Exception as exc:
        await asyncio.to_thread(library.mark_caption, image_id, "failed")
        logger.warning(f"图库图片 {image_id[:12]} 自动标签失败: {type(exc).__name__}")


async def periodic_gallery_maintenance() -> None:
    library = await asyncio.to_thread(get_image_library)
    try:
        report = await asyncio.to_thread(library.sync)
        if report["errors"]:
            logger.warning(f"图库扫描发现 {len(report['errors'])} 个无效文件，可在表情包图库中重新扫描查看")
    except (OSError, sqlite3.Error) as exc:
        logger.error(f"图库扫描失败: {exc}")
    while True:
        try:
            if _is_vlm_task_configured():
                items = await asyncio.to_thread(library.list_items)
                for item in items:
                    if item["caption_status"] == "pending":
                        await caption_library_image(item["id"])
        except (OSError, sqlite3.Error) as exc:
            logger.error(f"图库后台任务失败: {exc}")
        await asyncio.sleep(5)


def _search_candidates(query: str) -> List[Dict[str, Any]]:
    library = get_image_library()
    with get_db_session() as session:
        banned = set(
            session.exec(select(Images.image_hash).filter_by(image_type=ImageType.EMOJI, is_banned=True)).all()
        )
    return [item for item in library.candidates(query, library.max_images) if item["id"] not in banned][:16]


async def select_library_image(query: str, *, session_id: str = "") -> Optional[Dict[str, Any]]:
    candidates = await asyncio.to_thread(_search_candidates, query)
    if not candidates or not query.strip():
        return None
    summary = [{"id": item["id"], "filename": item["filename"], "tags": item["tags"]} for item in candidates]
    template = prompt_manager.get_prompt("gallery_search")
    template.add_context("request_data", json.dumps({"query": query, "images": summary}, ensure_ascii=False))
    prompt = await prompt_manager.render_prompt(template)
    try:
        async with asyncio.timeout(20):
            result = await LLMServiceClient(task_name="planner", request_type="emoji.gallery.search").generate_response(
                prompt,
                session_id=session_id,
            )
        choice = parse_llm_json(result.response)
        if not isinstance(choice, dict) or "id" not in choice:
            raise ValueError("检索模型未返回图片 ID")
        if choice["id"] is None:
            return None
        selected = next((item for item in candidates if item["id"] == choice["id"]), None)
        if selected is None:
            raise ValueError("检索模型返回了候选以外的图片 ID")
        return selected
    except Exception as exc:
        logger.warning(f"图库语义检索失败，使用标签匹配: {type(exc).__name__}")
        return next((item for item in candidates if item["score"] > 0), None)
