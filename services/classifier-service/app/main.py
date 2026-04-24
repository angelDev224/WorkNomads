import asyncio
import structlog

from app.consumer import start_consumer

logger = structlog.get_logger()

if __name__ == "__main__":
    asyncio.run(start_consumer())
