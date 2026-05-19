from datetime import datetime

from sqlalchemy import ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


# == Schema Information
#
# Table name: users
#
# id         : integer, primary key
# email      : varchar, not null
# profile_id : integer, -> profiles.id
# created_at : timestamp without time zone, not null, server_default=now()
#
# Indexes
#   ix_users_email (email) UNIQUE
#
# Foreign Keys
#   profile_id -> profiles.id (ON DELETE CASCADE)
#
# == End Schema Information

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    posts: Mapped[list["Post"]] = relationship(back_populates="author")  # noqa: F821
