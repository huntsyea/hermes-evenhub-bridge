import asyncio
from gateway.config import PlatformConfig
from .adapter import EvenG2Adapter


async def _main():
    adapter = EvenG2Adapter(PlatformConfig(extra={}))
    await adapter.connect()
    print(f"[evenhub-bridge] listening on port {adapter.bound_port}")
    await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(_main())
