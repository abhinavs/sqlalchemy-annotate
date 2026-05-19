from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


# == Schema Information
#
# Table name: profiles
#
# id  : integer, primary key
# bio : varchar(500)
#
# == End Schema Information

class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    bio: Mapped[str | None] = mapped_column(String(500))
