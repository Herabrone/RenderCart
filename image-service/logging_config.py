"""
Shared JSON logging configuration for the RenderCart image service.
Provides structured logging with correlation IDs and environment-driven log levels.
"""

import os
import logging
import json
import uuid
from typing import Optional

try:
    from pythonjsonlogger import jsonlogger
except ImportError:  # pragma: no cover - fallback for minimal dev environments
    jsonlogger = None


if jsonlogger:
    class JsonFormatter(jsonlogger.JsonFormatter):
        """Custom JSON formatter for structured logging."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._default_time_format = '%Y-%m-%dT%H:%M:%S.%fZ'
            self._default_msec_format = '%s%%03d'

        def add_fields(self, log_record, record, message_dict):
            super().add_fields(log_record, record, message_dict)
            if hasattr(record, 'correlation_id'):
                log_record['correlation_id'] = record.correlation_id
            log_record['service'] = 'rendercart'
            log_record['environment'] = os.getenv('ENVIRONMENT', 'development')
            log_record['version'] = '1.0.0'
else:
    class JsonFormatter(logging.Formatter):
        """Fallback formatter when python-json-logger is unavailable."""

        def format(self, record):
            payload = {
                "timestamp": self.formatTime(record, self.datefmt),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "service": "rendercart",
                "environment": os.getenv('ENVIRONMENT', 'development'),
                "version": "1.0.0",
            }
            correlation_id = getattr(record, "correlation_id", None)
            if correlation_id:
                payload["correlation_id"] = correlation_id
            for key, value in record.__dict__.items():
                if key.startswith("_") or key in payload:
                    continue
                if key in {
                    "name", "msg", "args", "levelname", "levelno", "pathname",
                    "filename", "module", "exc_info", "exc_text", "stack_info",
                    "lineno", "funcName", "created", "msecs", "relativeCreated",
                    "thread", "threadName", "process", "processName",
                }:
                    continue
                payload[key] = value
            return json.dumps(payload, default=str)


def get_log_level() -> str:
    """
    Get log level from environment variable.
    
    Returns:
        str: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
    
    # Validate log level
    valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
    if log_level not in valid_levels:
        logging.warning(f"Invalid LOG_LEVEL '{log_level}', defaulting to INFO")
        return 'INFO'
    
    return log_level


def setup_logging(correlation_id: Optional[str] = None) -> logging.Logger:
    """
    Setup structured JSON logging with correlation ID support.
    
    Args:
        correlation_id: Optional correlation ID to use for all logs
        
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger('rendercart')
    logger.setLevel(get_log_level())
    root_logger = logging.getLogger()
    root_logger.setLevel(get_log_level())
    
    # Prevent adding multiple handlers
    if root_logger.handlers:
        return logger
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(get_log_level())
    
    # Create JSON formatter
    if jsonlogger:
        formatter = JsonFormatter(
            '%(asctime)s %(levelname)s %(name)s %(message)s',
            rename_fields={
                'asctime': 'timestamp',
                'levelname': 'level',
                'name': 'logger',
                'message': 'message'
            }
        )
    else:
        formatter = JsonFormatter()
    console_handler.setFormatter(formatter)
    
    # Add handler to root logger so child loggers emit JSON consistently
    root_logger.addHandler(console_handler)
    
    # Set correlation ID if provided
    if correlation_id:
        logger.correlation_id = correlation_id
    
    return logger


def generate_correlation_id() -> str:
    """
    Generate a new correlation ID.
    
    Returns:
        str: UUID-based correlation ID
    """
    return str(uuid.uuid4())


def get_correlation_id() -> Optional[str]:
    """
    Get correlation ID from environment or generate new one.
    
    Returns:
        Optional[str]: Correlation ID if available, None otherwise
    """
    return os.getenv('CORRELATION_ID')


def set_correlation_id(correlation_id: str) -> None:
    """
    Set correlation ID in environment.
    
    Args:
        correlation_id: Correlation ID to set
    """
    os.environ['CORRELATION_ID'] = correlation_id


def log_event(
    logger: logging.Logger,
    event_type: str,
    job_id: Optional[str] = None,
    status: Optional[str] = None,
    message: Optional[str] = None,
    **extra_fields
) -> None:
    """
    Log a structured event with correlation ID.
    
    Args:
        logger: Logger instance
        event_type: Type of event (queued, download, preprocess, generate, upload, completed, retry, failed, webhook)
        job_id: Optional job ID
        status: Optional status
        message: Optional message
        extra_fields: Additional fields to include in log
    """
    log_data = {
        'event_type': event_type,
        'job_id': job_id,
        'status': status,
        'event_message': message,
        **extra_fields
    }
    
    # Remove None values and reserved LogRecord keys
    reserved_keys = {'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                     'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                     'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                     'thread', 'threadName', 'process', 'processName', 'message'}
    log_data = {k: v for k, v in log_data.items() if v is not None and k not in reserved_keys}
    
    logger.info(message or '', extra=log_data)
