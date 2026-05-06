from .config import AntinukeConfig
from .monitor import SlidingWindow, ServerSeverity
from .lockdown import LockdownManager
from .cog import AntiNuke

__all__ = [
    "AntinukeConfig",
    "SlidingWindow",
    "ServerSeverity",
    "LockdownManager",
    "AntiNuke",
]


async def setup(bot):
    await bot.add_cog(AntiNuke(bot))
