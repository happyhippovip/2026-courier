"""
Social Platform Client Interaction Layer
Provides client-side abstractions, HTTP REST API client, user session management,
interactive console, and CLI interface for interacting with the Social Platform.
"""

from .client import (
    SocialPlatformClient,
    SocialClient,
    ClientError,
    APIError,
    NotFoundError,
    ValidationError,
    AuthenticationError,
    ForbiddenError,
)
from .session import UserSession
from .cli import SocialCLI, main
from .interactive import InteractiveConsole

__all__ = [
    "SocialPlatformClient",
    "SocialClient",
    "UserSession",
    "SocialCLI",
    "InteractiveConsole",
    "main",
    "ClientError",
    "APIError",
    "NotFoundError",
    "ValidationError",
    "AuthenticationError",
    "ForbiddenError",
]
