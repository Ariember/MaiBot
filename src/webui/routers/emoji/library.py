"""表情包页面的额外图库接口。"""

from io import BytesIO

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from PIL import Image
from pydantic import BaseModel
from sqlmodel import select

import asyncio
import mimetypes

from src.common.data_models.image_data_model import MaiEmoji
from src.common.database.database import get_db_session
from src.common.database.database_model import Images, ImageType
from src.common.utils.image_path import resolve_stored_image_path
from src.config.config import global_config
from src.emoji_system.emoji_manager import emoji_manager
from src.emoji_system.image_gallery import MAX_IMAGE_BYTES, get_image_library
from src.webui.dependencies import require_auth

from .routes import _save_uploaded_emoji_file
from .support import generate_thumbnail

router = APIRouter(prefix="/emoji/library", tags=["emoji"], dependencies=[Depends(require_auth)])


class TagsRequest(BaseModel):
    tags: str


@router.get("")
def list_images(page: int = Query(1, ge=1), page_size: int = Query(24, ge=1, le=100), search: str = ""):
    library = get_image_library()
    items = library.list_items()
    filtered = [item for item in items if search.casefold() in " ".join([item["filename"], *item["tags"]]).casefold()]
    return {
        "items": filtered[(page - 1) * page_size : page * page_size],
        "total": len(filtered),
        "pending": sum(item["caption_status"] == "pending" for item in items),
        "failed": sum(item["caption_status"] == "failed" for item in items),
        "directory": str(library.images),
    }


@router.post("/upload")
async def upload_image(file: UploadFile = File(...), tags: str = Form("")):
    try:
        data = await file.read(MAX_IMAGE_BYTES + 1)
    finally:
        await file.close()
    library = await asyncio.to_thread(get_image_library)
    try:
        item, added = await asyncio.to_thread(library.add_bytes, data, file.filename or "图片", tags)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"item": item, "added": added}


@router.post("/sync")
def sync_images():
    return get_image_library().sync()


@router.post("/retry-tags")
def retry_tags():
    library = get_image_library()
    count = 0
    for item in library.list_items():
        if item["caption_status"] == "failed":
            library.mark_caption(item["id"], "pending")
            count += 1
    return {"queued": count}


def _get_item(image_id: str):
    try:
        return get_image_library().get(image_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="图库图片不存在") from exc


@router.get("/{image_id}/content")
def image_content(image_id: str, original: bool = False):
    library = get_image_library()
    item = _get_item(image_id)
    path = library.root / item["rel_path"]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="图片文件不存在，请重新扫描图库")
    if not original:
        return FileResponse(generate_thumbnail(str(path), image_id), media_type="image/webp")
    return FileResponse(path, media_type=mimetypes.guess_type(str(path))[0] or "application/octet-stream")


@router.patch("/{image_id}")
def update_tags(image_id: str, request: TagsRequest):
    _get_item(image_id)
    get_image_library().set_tags(image_id, request.tags)
    return {"saved": True}


@router.delete("/{image_id}")
def delete_image(image_id: str):
    _get_item(image_id)
    get_image_library().delete(image_id)
    return {"deleted": True}


def _prepare_emoji(image_id: str) -> MaiEmoji:
    library = get_image_library()
    item = _get_item(image_id)
    with get_db_session() as session:
        record = session.exec(select(Images).filter_by(image_hash=image_id, image_type=ImageType.EMOJI)).first()
        if record is not None and record.is_banned:
            raise HTTPException(status_code=400, detail="此图片已被丢弃，请先在表情包中解除封禁")
        if (
            record is not None
            and record.is_registered
            and not record.no_file_flag
            and resolve_stored_image_path(record.full_path).is_file()
        ):
            return MaiEmoji.from_db_instance(record)
    if len(emoji_manager.emojis) >= global_config.emoji.max_reg_num:
        raise HTTPException(status_code=409, detail="表情包已达注册上限，请先取消注册部分表情")
    data = library.read_bytes(image_id)
    with Image.open(BytesIO(data)) as image:
        image_format = image.format.lower()
    emoji = MaiEmoji(library.root / item["rel_path"], image_bytes=data)
    emoji.file_hash = image_id
    emoji.image_format = image_format
    emoji.description = ",".join(item["tags"])
    emoji.emotion = item["tags"]
    return emoji


@router.post("/{image_id}/adopt")
async def adopt_image(image_id: str):
    try:
        emoji = await asyncio.to_thread(_prepare_emoji, image_id)
        if not await emoji_manager.review_emoji_for_registration(emoji):
            raise HTTPException(status_code=400, detail="图片未通过表情包内容审核")
        library = await asyncio.to_thread(get_image_library)
        if emoji.full_path.is_relative_to(library.images):
            path = await asyncio.to_thread(_save_uploaded_emoji_file, emoji.image_bytes, image_id, emoji.image_format)
            emoji._set_full_path(resolve_stored_image_path(path))
        status = await asyncio.to_thread(emoji_manager.register_emoji_to_db, emoji)
        if status == "failed":
            raise HTTPException(status_code=500, detail="图库图片注册失败")
        if not emoji_manager.get_emoji_by_hash(image_id):
            emoji_manager.emojis.append(emoji)
            emoji_manager._emoji_num = len(emoji_manager.emojis)
        return {"registered": True}
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=400, detail="图片文件不可用，请重新扫描图库") from exc
