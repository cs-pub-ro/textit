import logging
import os
from typing import Generic, TypeVar, Callable, Optional
import sys

T = TypeVar('T')
U = TypeVar('U')

# Set up logging
log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

# Create a logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Check if the logger already has handlers to avoid duplicate logging
if not logger.handlers:
    # Add a file handler with the PID in the filename
    pid = os.getpid()
    file_handler = logging.FileHandler(f"{log_dir}/{pid}.err")
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Add a stream handler to print to stderr
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # Prevent the logger from propagating messages to the root logger
    logger.propagate = False

class Result(Generic[T]):
    def __init__(self, value: Optional[T], error: Optional[str]):
        self._value = value
        self._error = error

    @classmethod
    def ok(cls, value: T) -> 'Result[T]':
        return cls(value, None)

    @classmethod
    def err(cls, error: str) -> 'Result[T]':
        logger.error(f"Error occurred: {error}")
        return cls(None, error)

    def is_ok(self) -> bool:
        return self._error is None

    def is_err(self) -> bool:
        return self._error is not None

    def unwrap(self) -> T:
        if self.is_err():
            raise ValueError(self._error)
        return self._value

    def unwrap_or(self, default: T) -> T:
        return self._value if self.is_ok() else default

    def map(self, func: Callable[[T], U]) -> 'Result[U]':
        if self.is_ok():
            return Result.ok(func(self._value))
        return Result.err(self._error)

    def and_then(self, func: Callable[[T], 'Result[U]']) -> 'Result[U]':
        if self.is_ok():
            return func(self._value)
        return Result.err(self._error)

    def unwrap_or_else(self, func: Callable[[str], T]) -> T:
        if self.is_ok():
            return self._value
        return func(self._error)

def handle_result(result: Result[T], success_message: str) -> None:
    result.map(lambda texts: print(f"{success_message}\n" + "\n".join(texts))) \
          .unwrap_or_else(lambda error: print(f"Error: {error}"))
