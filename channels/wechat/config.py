"""个人微信渠道配置：从 .env 读取"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

DEFAULT_BASE_URL = "https://ilinkai.weixin.qq.com"


@dataclass(frozen=True)
class WechatConfig:
    base_url: str = DEFAULT_BASE_URL

    @classmethod
    def from_env(cls) -> "WechatConfig":
        return cls(
            base_url=os.getenv("WECHAT_ILINK_BASE_URL", DEFAULT_BASE_URL),
        )
