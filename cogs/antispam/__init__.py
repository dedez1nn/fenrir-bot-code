from .config import AntispamConfig
from .storage import JSONStorage
from .scoring import ScoreManager
from .detector import Detector, Violation
from .punisher import Punisher, Action
from .audit import AuditLogger
from .cog import AntiSpam

__all__ = [
    "AntispamConfig",
    "JSONStorage",
    "ScoreManager",
    "Detector",
    "Violation",
    "Punisher",
    "Action",
    "AuditLogger",
    "AntiSpam",
]


async def setup(bot):
    await bot.add_cog(AntiSpam(bot))
