
from core.logging_config import setup_logging

def test_logger_init():
    logger = setup_logging()
    logger.info("hello")
    assert logger.name == "ptcg"
