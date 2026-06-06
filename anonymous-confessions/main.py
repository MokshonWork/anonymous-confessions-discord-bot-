"""Entrypoint so you can run `python main.py`."""
from bot.bot import main
import asyncio

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
