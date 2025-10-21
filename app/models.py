from __future__ import annotations
from datetime import datetime
from typing import List
from sqlalchemy import String, Integer, ForeignKey, Table, Text, DateTime, func, Column
from sqlalchemy.orm import relationship, Mapped, mapped_column
from .database import Base

chat_users = Table(
    "chat_users",
    Base.metadata,
    Column("chat_id", ForeignKey("chats.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password: Mapped[str] = mapped_column(String)

    chats: Mapped[List["Chat"]] = relationship(
        secondary=chat_users, back_populates="participants"
    )
    messages: Mapped[List["Message"]] = relationship(
        back_populates="author", cascade="all, delete-orphan"
    )

class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    owner: Mapped["User"] = relationship()
    participants: Mapped[List["User"]] = relationship(
        secondary=chat_users, back_populates="chats"
    )
    messages: Mapped[List["Message"]] = relationship(
        back_populates="chat", cascade="all, delete-orphan", order_by="Message.created_at"
    )

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    chat_id: Mapped[int] = mapped_column(ForeignKey("chats.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    chat: Mapped["Chat"] = relationship(back_populates="messages")
    author: Mapped["User"] = relationship(back_populates="messages")