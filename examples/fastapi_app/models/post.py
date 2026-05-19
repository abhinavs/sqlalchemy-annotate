import enum

from sqlalchemy import Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class PostStatus(enum.Enum):
    draft = "draft"
    published = "published"


# == Schema Information
#
# Table name: posts
#
# id        : integer, primary key
# title     : varchar(200), not null
# status    : poststatus, not null, enum(draft, published), default=PostStatus.draft
# author_id : integer, not null, -> users.id
#
# Foreign Keys
#   author_id -> users.id
#
# == End Schema Information

class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus), default=PostStatus.draft
    )
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    author: Mapped["User"] = relationship(back_populates="posts")  # noqa: F821
