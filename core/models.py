"""定义 QQ 消息传输模型。"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class QQMessageTarget:
    """QQ 消息发送目标。"""

    kind: Literal["group", "user", "channel", "direct"]
    target_id: str
    guild_id: str = ""

    @property
    def route_key(self) -> str:
        """返回用于隔离被动回复上下文的稳定路由键。"""

        return f"{self.kind}:{self.target_id}:{self.guild_id}"


@dataclass(frozen=True)
class PassiveReplyContext:
    """某个聊天目标最近一次可用于被动回复的消息。"""

    message_id: str
    expire_at: float


@dataclass(frozen=True)
class OutboundMedia:
    """待上传到 QQ 富媒体接口的媒体。"""

    file_type: int
    file_data: str = ""
    url: str = ""
    name: str = ""
