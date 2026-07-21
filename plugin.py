"""QQ 官方机器人适配器插件入口。"""

from __future__ import annotations

from .core import QQOfficialAdapterPlugin


def create_plugin() -> QQOfficialAdapterPlugin:
    """创建 QQ 官方机器人适配器插件实例。"""

    return QQOfficialAdapterPlugin()
