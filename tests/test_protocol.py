from pathlib import Path

import asyncio
import json

import pytest

from core.client import QQAPIClientMixin
from core.models import QQMessageTarget
from core.settings import QQOfficialAdapterSettings


PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def test_all_message_scenario_urls() -> None:
    base_url = "https://api.sgroup.qq.com"

    assert (
        QQAPIClientMixin._message_url(base_url, QQMessageTarget(kind="user", target_id="user-openid"))
        == f"{base_url}/v2/users/user-openid/messages"
    )
    assert (
        QQAPIClientMixin._message_url(base_url, QQMessageTarget(kind="group", target_id="group-openid"))
        == f"{base_url}/v2/groups/group-openid/messages"
    )
    assert (
        QQAPIClientMixin._message_url(base_url, QQMessageTarget(kind="channel", target_id="channel-id"))
        == f"{base_url}/channels/channel-id/messages"
    )
    assert (
        QQAPIClientMixin._message_url(
            base_url,
            QQMessageTarget(kind="direct", target_id="user-id", guild_id="guild-id"),
        )
        == f"{base_url}/dms/guild-id/messages"
    )


def test_passive_reply_sequence_stops_after_platform_limit() -> None:
    async def run_scenario() -> None:
        client = QQAPIClientMixin()
        client._seq_lock = asyncio.Lock()
        client._reply_sequences = {}
        target = QQMessageTarget(kind="group", target_id="group-openid")

        for expected_seq in range(1, 6):
            body = {}
            await client._add_reply_fields(body, target, "message-id")
            assert body == {"msg_id": "message-id", "msg_seq": expected_seq}

        with pytest.raises(RuntimeError, match="平台上限 5"):
            await client._add_reply_fields({}, target, "message-id")

    asyncio.run(run_scenario())


def test_private_passive_reply_limit_is_four() -> None:
    async def run_scenario() -> None:
        client = QQAPIClientMixin()
        client._seq_lock = asyncio.Lock()
        client._reply_sequences = {}
        target = QQMessageTarget(kind="user", target_id="user-openid")

        for expected_seq in range(1, 5):
            body = {}
            await client._add_reply_fields(body, target, "message-id")
            assert body == {"msg_id": "message-id", "msg_seq": expected_seq}

        with pytest.raises(RuntimeError, match="平台上限 4"):
            await client._add_reply_fields({}, target, "message-id")

    asyncio.run(run_scenario())


def test_user_configuration_does_not_expose_connection_details() -> None:
    schema = QQOfficialAdapterSettings.model_json_schema()

    assert set(schema["properties"]) == {"plugin", "credentials", "chat"}
    credentials_ref = schema["properties"]["credentials"]["$ref"].split("/")[-1]
    sandbox_schema = schema["$defs"][credentials_ref]["properties"]["sandbox"]
    assert sandbox_schema["hidden"] is True


def test_manifest_uses_local_icon_and_current_version() -> None:
    manifest = json.loads((PLUGIN_ROOT / "_manifest.json").read_text(encoding="utf-8"))

    assert manifest["version"] == "1.1.1"
    assert manifest["display"]["icon"]["value"] == "assets/icon.png"
    assert (PLUGIN_ROOT / "assets" / "icon.png").is_file()
