"""SQLAlchemy ORM models."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.db import Base


class Material(Base):
    """A collectible production material."""

    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    logs: Mapped[list["ProductionLog"]] = relationship(back_populates="material")


class ProductionLog(Base):
    """One production observation."""

    __tablename__ = "production_logs"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_quantity_positive"),
        CheckConstraint("red_quantity >= 0", name="ck_red_nonnegative"),
        CheckConstraint("red_quantity <= quantity", name="ck_red_lte_quantity"),
        CheckConstraint("skill_level IN (9, 10, 11, 12)", name="ck_skill_level"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    datetime: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"), index=True)
    skill_level: Mapped[int] = mapped_column(Integer, index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    red_quantity: Mapped[int] = mapped_column(Integer)
    remark: Mapped[str] = mapped_column(Text, default="")
    material: Mapped[Material] = relationship(back_populates="logs")


class Setting(Base):
    """Persistent string application setting."""

    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
