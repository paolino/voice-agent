"""Entry point for voice-agent."""

import logging
import sys

from voice_agent.bot import VoiceAgentBot
from voice_agent.config import load_settings


def main() -> None:
    """Run the voice agent bot."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        settings = load_settings()
    except Exception as e:
        logging.error("Failed to load settings: %s", e)
        sys.exit(1)

    bot = VoiceAgentBot(settings)
    bot.run()


if __name__ == "__main__":
    main()
