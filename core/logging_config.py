
import logging
from logging import Logger

DEFAULT_FORMAT = "[%(asctime)s] %(levelname)s %(name)s: %(message)s"
DEFAULT_DATEFMT = "%H:%M:%S"

def setup_logging(level: int = logging.INFO) -> Logger:
    logging.basicConfig(level=level, format=DEFAULT_FORMAT, datefmt=DEFAULT_DATEFMT)
    logger = logging.getLogger("ptcg")
    logger.debug("Logging initialized.")
    return logger
