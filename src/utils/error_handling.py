"""Error handling and logging infrastructure."""

import logging
import logging.handlers
import os
import sys
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
) -> None:
    """Configure logging with structured format and optional file rotation.

    Args:
        level: Logging level (e.g., logging.INFO).
        log_file: Path to log file. If None, only logs to stdout.
        max_bytes: Maximum size of log file before rotation.
        backup_count: Number of backup files to keep.
    """
    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Clear any existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (if log_file specified)
    if log_file:
        # Ensure log directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)

        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=max_bytes, backupCount=backup_count
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name.

    Args:
        name: Logger name (usually __name__).

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)


# Exception classes for the application
class DeFiAnalyticsError(Exception):
    """Base exception for DeFi Analytics Tool."""


class ConfigurationError(DeFiAnalyticsError):
    """Raised when there is a configuration error."""


class DataFetchError(DeFiAnalyticsError):
    """Raised when fetching data from external sources fails."""


class CalculationError(DeFiAnalyticsError):
    """Raised when calculations fail."""


class ValidationError(DeFiAnalyticsError):
    """Raised when input validation fails."""


class SimulationError(DeFiAnalyticsError):
    """Raised when transaction simulation fails."""


# Example usage
if __name__ == "__main__":
    # Setup logging to file and console
    setup_logging(level=logging.DEBUG, log_file="logs/defi_tool.log")
    logger = get_logger(__name__)
    logger.debug("Debug message")
    logger.info("Info message")
    logger.warning("Warning message")
    logger.error("Error message")
