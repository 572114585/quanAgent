"""ilink Bot API 类型定义"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class MessageType(IntEnum):
    USER = 1
    BOT = 2


class MessageItemType(IntEnum):
    TEXT = 1
    IMAGE = 2
    VOICE = 3
    FILE = 4
    VIDEO = 5


class MessageState(IntEnum):
    NEW = 0
    GENERATING = 1
    FINISH = 2


class TypingStatus(IntEnum):
    TYPING = 1
    CANCEL = 2


class UploadMediaType(IntEnum):
    IMAGE = 1
    VIDEO = 2
    FILE = 3
    VOICE = 4


@dataclass
class TextItem:
    text: str = ""


@dataclass
class ImageItem:
    url: str = ""
    aeskey: str = ""
    encrypt_query_param: str = ""
    aes_key: str = ""
    encrypt_type: int = 0
    mid_size: int = 0
    hd_size: int = 0


@dataclass
class VoiceItem:
    text: str = ""
    encrypt_query_param: str = ""
    aes_key: str = ""


@dataclass
class FileItem:
    file_name: str = ""
    len: str = "0"
    encrypt_query_param: str = ""
    aes_key: str = ""
    encrypt_type: int = 0


@dataclass
class MessageItem:
    type: MessageItemType = MessageItemType.TEXT
    text_item: TextItem = field(default_factory=TextItem)
    image_item: ImageItem = field(default_factory=ImageItem)
    voice_item: VoiceItem = field(default_factory=VoiceItem)
    file_item: FileItem = field(default_factory=FileItem)


@dataclass
class WeixinMessage:
    seq: int = 0
    message_id: int = 0
    from_user_id: str = ""
    to_user_id: str = ""
    create_time_ms: int = 0
    message_type: MessageType = MessageType.USER
    message_state: MessageState = MessageState.NEW
    item_list: list[MessageItem] = field(default_factory=list)
    context_token: str = ""


def parse_message(raw: dict) -> WeixinMessage:
    """从 API 原始 JSON 解析 WeixinMessage"""
    items = []
    for raw_item in raw.get("item_list") or []:
        item_type = MessageItemType(raw_item.get("type", 1))
        text_item = TextItem(**(raw_item.get("text_item") or {}))
        image_raw = raw_item.get("image_item") or {}
        # image_item 可能有嵌套的 media 字段
        media = image_raw.pop("media", {}) if isinstance(image_raw, dict) else {}
        if media:
            image_raw.setdefault("encrypt_query_param", media.get("encrypt_query_param", ""))
            image_raw.setdefault("aes_key", media.get("aes_key", ""))
            image_raw.setdefault("encrypt_type", media.get("encrypt_type", 0))
        image_item = ImageItem(**{k: v for k, v in image_raw.items() if hasattr(ImageItem, k)})
        voice_raw = raw_item.get("voice_item") or {}
        voice_media = voice_raw.pop("media", {}) if isinstance(voice_raw, dict) else {}
        if voice_media:
            voice_raw.setdefault("encrypt_query_param", voice_media.get("encrypt_query_param", ""))
            voice_raw.setdefault("aes_key", voice_media.get("aes_key", ""))
        voice_item = VoiceItem(**{k: v for k, v in voice_raw.items() if hasattr(VoiceItem, k)})
        file_raw = raw_item.get("file_item") or {}
        file_media = file_raw.pop("media", {}) if isinstance(file_raw, dict) else {}
        if file_media:
            file_raw.setdefault("encrypt_query_param", file_media.get("encrypt_query_param", ""))
            file_raw.setdefault("aes_key", file_media.get("aes_key", ""))
            file_raw.setdefault("encrypt_type", file_media.get("encrypt_type", 0))
        file_item = FileItem(**{k: v for k, v in file_raw.items() if hasattr(FileItem, k)})
        items.append(MessageItem(
            type=item_type,
            text_item=text_item,
            image_item=image_item,
            voice_item=voice_item,
            file_item=file_item,
        ))

    return WeixinMessage(
        seq=raw.get("seq", 0),
        message_id=raw.get("message_id", 0),
        from_user_id=raw.get("from_user_id", ""),
        to_user_id=raw.get("to_user_id", ""),
        create_time_ms=raw.get("create_time_ms", 0),
        message_type=MessageType(raw.get("message_type", 1)),
        message_state=MessageState(raw.get("message_state", 0)),
        item_list=items,
        context_token=raw.get("context_token", ""),
    )
