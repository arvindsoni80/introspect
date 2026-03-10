"""Data access layer."""

from .database import Database, init_database
from .repository import Repository

__all__ = [
    'Database',
    'init_database',
    'Repository',
]
