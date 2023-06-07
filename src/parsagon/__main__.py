import logging
import sys

from src.parsagon.main import main

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        prompt = sys.argv[1]
    except IndexError:
        logger.error("Usage python3 -m parsagon <prompt>")

    main(prompt)
