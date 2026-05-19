"""Example model package. Run from examples/fastapi_app:

    sqlalchemy-annotate generate --models models
"""

from models.base import Base
from models.post import Post
from models.profile import Profile
from models.user import User

__all__ = ["Base", "User", "Post", "Profile"]
