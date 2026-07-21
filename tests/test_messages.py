from types import SimpleNamespace

import asyncio
import base64

from core.constants import EVENT_GROUP_AT_MESSAGE_CREATE, EVENT_GROUP_MESSAGE_CREATE
from core.messages import QQMessageMixin
from core.settings import QQOfficialAdapterSettings


class _Logger:
    def warning(self, message: str) -> None:
        del message


class _MessageAdapter(QQMessageMixin):
    def __init__(self) -> None:
        self._connected_account_id = "bot-user-id"
        self._connected_account_name = "机器人1904288168"
        self._bot_mention_ids = set()
        self._settings = QQOfficialAdapterSettings(credentials={"appid": "1904288168", "app_secret": "secret"})
        self.ctx = SimpleNamespace(logger=_Logger())
        self._passive_replies = {}
        self._reply_sequences = {}
        self._seen_inbound_message_ids = {}

    def _load_settings(self) -> QQOfficialAdapterSettings:
        return self._settings

    async def _download_attachment(self, url: str) -> bytes:
        assert url == "https://example.com/image.png"
        return b"image-bytes"


def test_pure_image_does_not_send_placeholder_text() -> None:
    message = {
        "raw_message": [
            {
                "type": "image",
                "data": "[图片]",
                "binary_data_base64": base64.b64encode(b"image").decode("ascii"),
            }
        ],
        "processed_plain_text": "[图片]",
        "is_picture": True,
    }

    assert QQMessageMixin._extract_outbound_text(message) == ""


def test_mixed_message_only_extracts_real_text() -> None:
    message = {
        "raw_message": [
            {"type": "text", "data": "说明文字"},
            {
                "type": "image",
                "data": "[图片]",
                "binary_data_base64": base64.b64encode(b"image").decode("ascii"),
            },
        ],
        "processed_plain_text": "说明文字 [图片]",
    }

    assert QQMessageMixin._extract_outbound_text(message) == "说明文字"


def test_outbound_at_component_uses_qq_mention_syntax() -> None:
    message = {
        "raw_message": [
            {"type": "at", "data": {"target_user_id": "member-openid"}},
            {"type": "text", "data": " 你好"},
        ]
    }

    assert QQMessageMixin._extract_outbound_text(message) == "<@member-openid> 你好"


def test_emoji_uses_image_media_type_and_real_base64() -> None:
    encoded = base64.b64encode(b"emoji-image").decode("ascii")
    message = {
        "raw_message": [
            {
                "type": "emoji",
                "data": "[表情]",
                "binary_data_base64": encoded,
            }
        ]
    }

    media = QQMessageMixin._extract_outbound_media(message)

    assert len(media) == 1
    assert media[0].file_type == 1
    assert media[0].file_data == encoded


def test_hash_and_placeholder_are_not_treated_as_media() -> None:
    message = {
        "raw_message": [
            {"type": "image", "data": "[图片]", "hash": "a" * 64},
            {"type": "emoji", "data": "[表情]"},
        ]
    }

    assert QQMessageMixin._extract_outbound_media(message) == []


def test_group_at_event_does_not_require_configured_self_id() -> None:
    adapter = _MessageAdapter()
    adapter._connected_account_id = ""
    adapter._settings = QQOfficialAdapterSettings(credentials={"appid": "", "app_secret": "secret"})

    assert adapter._is_bot_mentioned(EVENT_GROUP_AT_MESSAGE_CREATE, {}, "消息") is True


def test_full_group_event_detects_bot_mention_from_elements() -> None:
    adapter = _MessageAdapter()
    data = {
        "msg_elements": [
            {
                "element_type": "at",
                "at_element": {"target_id": "bot-user-id"},
            }
        ]
    }

    assert adapter._is_bot_mentioned(EVENT_GROUP_MESSAGE_CREATE, data, "消息") is True


def test_full_group_event_detects_bot_flagged_mention() -> None:
    adapter = _MessageAdapter()
    data = {
        "mentions": [
            {
                "id": "group-scoped-bot-id",
                "username": "机器人1904288168",
                "bot": True,
            }
        ]
    }

    assert adapter._is_bot_mentioned(EVENT_GROUP_MESSAGE_CREATE, data, "消息") is True
    assert "group-scoped-bot-id" in adapter._bot_mention_ids
    assert adapter._remove_bot_mention_tokens("<@group-scoped-bot-id> 消息") == "消息"


def test_full_group_event_does_not_confuse_another_bot() -> None:
    adapter = _MessageAdapter()
    data = {
        "mentions": [
            {
                "id": "another-bot-id",
                "username": "另一个机器人",
                "bot": True,
            }
        ]
    }

    assert adapter._is_bot_mentioned(EVENT_GROUP_MESSAGE_CREATE, data, "消息") is False


def test_bot_identity_only_matches_current_connection() -> None:
    adapter = _MessageAdapter()

    assert adapter._is_current_bot_identity({"id": "bot-user-id", "bot": True}) is True
    assert adapter._is_current_bot_identity({"username": "机器人1904288168", "bot": True}) is True
    assert adapter._is_current_bot_identity({"id": "another-bot-id", "username": "另一个机器人", "bot": True}) is False


def test_inbound_image_contains_binary_payload() -> None:
    adapter = _MessageAdapter()
    data = {
        "id": "message-id",
        "author": {"member_openid": "member-openid"},
        "content": "图片",
        "group_openid": "group-openid",
        "timestamp": "2026-07-21T22:00:00+08:00",
        "attachments": [
            {
                "content_type": "image/png",
                "filename": "image.png",
                "url": "https://example.com/image.png",
            }
        ],
    }

    message = asyncio.run(adapter._build_inbound_message_dict(EVENT_GROUP_MESSAGE_CREATE, data))

    image_segment = message["raw_message"][1]
    assert image_segment["type"] == "image"
    assert base64.b64decode(image_segment["binary_data_base64"]) == b"image-bytes"
    assert message["is_picture"] is True
    assert message["message_info"]["additional_config"]["platform_io_account_id"] == "bot-user-id"


def test_inbound_sticker_is_not_duplicated_as_placeholder_text() -> None:
    adapter = _MessageAdapter()
    data = {
        "id": "sticker-message-id",
        "author": {"member_openid": "member-openid"},
        "content": "[表情]",
        "group_openid": "group-openid",
        "attachments": [
            {
                "content_type": "image/png",
                "filename": "sticker.png",
                "url": "https://example.com/image.png",
                "type": "sticker",
            }
        ],
    }

    message = asyncio.run(adapter._build_inbound_message_dict(EVENT_GROUP_MESSAGE_CREATE, data))

    assert len(message["raw_message"]) == 1
    assert message["raw_message"][0]["type"] == "emoji"
    assert message["processed_plain_text"] == "[表情]"
    assert message["is_emoji"] is True


def test_attachment_protocol_tag_is_not_exposed_as_text() -> None:
    adapter = _MessageAdapter()
    data = {
        "id": "image-message-id",
        "author": {"member_openid": "member-openid"},
        "content": '<attachmentType="image/png",attachmentIndex=0,description="W+WbvueJh10=">',
        "group_openid": "group-openid",
        "attachments": [
            {
                "content_type": "image/png",
                "filename": "image.png",
                "url": "https://example.com/image.png",
            }
        ],
    }

    message = asyncio.run(adapter._build_inbound_message_dict(EVENT_GROUP_MESSAGE_CREATE, data))

    assert len(message["raw_message"]) == 1
    assert message["raw_message"][0]["type"] == "image"
    assert message["processed_plain_text"] == "[图片]"


def test_native_qq_face_is_exposed_as_emoji_summary() -> None:
    adapter = _MessageAdapter()
    data = {
        "id": "face-message-id",
        "author": {"member_openid": "member-openid"},
        "content": '<faceType=6,faceId="0",ext="eyJ0ZXh0IjoiIn0=">',
        "group_openid": "group-openid",
    }

    message = asyncio.run(adapter._build_inbound_message_dict(EVENT_GROUP_MESSAGE_CREATE, data))

    assert message["raw_message"] == [{"type": "text", "data": "[表情]"}]
    assert message["processed_plain_text"] == "[表情]"
    assert message["is_emoji"] is True
