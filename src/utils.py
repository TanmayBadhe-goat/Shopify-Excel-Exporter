import logging
from logging.handlers import RotatingFileHandler


def setup_logging():
    """Configure logging with rotation (5 MB max per file, keep 3 backups)."""
    handler = RotatingFileHandler("app.log", maxBytes=5 * 1024 * 1024, backupCount=3)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    logging.basicConfig(
        level=logging.INFO,
        handlers=[handler, console],
    )
    return logging.getLogger(__name__)


logger = setup_logging()
