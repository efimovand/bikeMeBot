from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Integer,
    String, Text, UniqueConstraint, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------

class Location(Base):
    __tablename__ = "location"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))    # forest / street / track
    prompt: Mapped[str] = mapped_column(Text)

    bikes: Mapped[list["Bike"]] = relationship(back_populates="location")


# ---------------------------------------------------------------------------
# Bike
# ---------------------------------------------------------------------------

class Bike(Base):
    __tablename__ = "bike"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(50))
    location_id: Mapped[int] = mapped_column(ForeignKey("location.id"))
    prompt: Mapped[str] = mapped_column(Text)

    location: Mapped["Location"] = relationship(back_populates="bikes")
    colors: Mapped[list["BikeColor"]] = relationship(back_populates="bike")
    files: Mapped[list["BikeFile"]] = relationship(back_populates="bike")


class BikeColor(Base):
    __tablename__ = "bike_color"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    # null = доступен для всех байков; не null = только для конкретного
    bike_id: Mapped[int | None] = mapped_column(ForeignKey("bike.id"), nullable=True)

    bike: Mapped["Bike | None"] = relationship(back_populates="colors")


class BikeFile(Base):
    __tablename__ = "bike_file"
    __table_args__ = (
        UniqueConstraint("bike_id", "color_id", name="uq_bike_file_bike_color"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bike_id: Mapped[int] = mapped_column(ForeignKey("bike.id"))
    color_id: Mapped[int] = mapped_column(ForeignKey("bike_color.id"))
    description: Mapped[str] = mapped_column(String(255))  # "X цвета Y / X в расцветке Y"
    file: Mapped[str] = mapped_column(Text)                # url на png на диске

    bike: Mapped["Bike"] = relationship(back_populates="files")
    color: Mapped["BikeColor"] = relationship()


# ---------------------------------------------------------------------------
# Helmet
# ---------------------------------------------------------------------------

class Helmet(Base):
    __tablename__ = "helmet"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(50))
    prompt: Mapped[str] = mapped_column(Text)

    colors: Mapped[list["HelmetColor"]] = relationship(back_populates="helmet")
    files: Mapped[list["HelmetFile"]] = relationship(back_populates="helmet")


class HelmetColor(Base):
    __tablename__ = "helmet_color"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    helmet_id: Mapped[int | None] = mapped_column(ForeignKey("helmet.id"), nullable=True)

    helmet: Mapped["Helmet | None"] = relationship(back_populates="colors")


class HelmetFile(Base):
    __tablename__ = "helmet_file"
    __table_args__ = (
        UniqueConstraint("helmet_id", "color_id", name="uq_helmet_file_helmet_color"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    helmet_id: Mapped[int] = mapped_column(ForeignKey("helmet.id"))
    color_id: Mapped[int] = mapped_column(ForeignKey("helmet_color.id"))
    description: Mapped[str] = mapped_column(String(255))
    file: Mapped[str] = mapped_column(Text)

    helmet: Mapped["Helmet"] = relationship(back_populates="files")
    color: Mapped["HelmetColor"] = relationship()


# ---------------------------------------------------------------------------
# Jacket
# ---------------------------------------------------------------------------

class Jacket(Base):
    __tablename__ = "jacket"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(50))
    prompt: Mapped[str] = mapped_column(Text)

    colors: Mapped[list["JacketColor"]] = relationship(back_populates="jacket")
    files: Mapped[list["JacketFile"]] = relationship(back_populates="jacket")


class JacketColor(Base):
    __tablename__ = "jacket_color"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    jacket_id: Mapped[int | None] = mapped_column(ForeignKey("jacket.id"), nullable=True)

    jacket: Mapped["Jacket | None"] = relationship(back_populates="colors")


class JacketFile(Base):
    __tablename__ = "jacket_file"
    __table_args__ = (
        UniqueConstraint("jacket_id", "color_id", name="uq_jacket_file_jacket_color"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jacket_id: Mapped[int] = mapped_column(ForeignKey("jacket.id"))
    color_id: Mapped[int] = mapped_column(ForeignKey("jacket_color.id"))
    description: Mapped[str] = mapped_column(String(255))
    file: Mapped[str] = mapped_column(Text)

    jacket: Mapped["Jacket"] = relationship(back_populates="files")
    color: Mapped["JacketColor"] = relationship()


# ---------------------------------------------------------------------------
# Glove
# ---------------------------------------------------------------------------

class Glove(Base):
    __tablename__ = "glove"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    brand: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(50))
    prompt: Mapped[str] = mapped_column(Text)

    colors: Mapped[list["GloveColor"]] = relationship(back_populates="glove")
    files: Mapped[list["GloveFile"]] = relationship(back_populates="glove")


class GloveColor(Base):
    __tablename__ = "glove_color"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    glove_id: Mapped[int | None] = mapped_column(ForeignKey("glove.id"), nullable=True)

    glove: Mapped["Glove | None"] = relationship(back_populates="colors")


class GloveFile(Base):
    __tablename__ = "glove_file"
    __table_args__ = (
        UniqueConstraint("glove_id", "color_id", name="uq_glove_file_glove_color"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    glove_id: Mapped[int] = mapped_column(ForeignKey("glove.id"))
    color_id: Mapped[int] = mapped_column(ForeignKey("glove_color.id"))
    description: Mapped[str] = mapped_column(String(255))
    file: Mapped[str] = mapped_column(Text)

    glove: Mapped["Glove"] = relationship(back_populates="files")
    color: Mapped["GloveColor"] = relationship()


# ---------------------------------------------------------------------------
# Account (токены KIE AI)
# ---------------------------------------------------------------------------

class Account(Base):
    __tablename__ = "account"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    spent_stars: Mapped[int] = mapped_column(Integer, default=0)

    # Текущий конфигуратор пользователя
    bike_file_id: Mapped[int | None] = mapped_column(ForeignKey("bike_file.id"), nullable=True)
    helmet_file_id: Mapped[int | None] = mapped_column(ForeignKey("helmet_file.id"), nullable=True)
    jacket_file_id: Mapped[int | None] = mapped_column(ForeignKey("jacket_file.id"), nullable=True)
    glove_file_id: Mapped[int | None] = mapped_column(ForeignKey("glove_file.id"), nullable=True)

    bike_file: Mapped["BikeFile | None"] = relationship(foreign_keys=[bike_file_id])
    helmet_file: Mapped["HelmetFile | None"] = relationship(foreign_keys=[helmet_file_id])
    jacket_file: Mapped["JacketFile | None"] = relationship(foreign_keys=[jacket_file_id])
    glove_file: Mapped["GloveFile | None"] = relationship(foreign_keys=[glove_file_id])
    photoset: Mapped["UserPhotoset | None"] = relationship(back_populates="user", uselist=False)
    generations: Mapped[list["Generation"]] = relationship(back_populates="user")


class UserPhotoset(Base):
    __tablename__ = "user_photoset"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), unique=True)
    front_photo: Mapped[str | None] = mapped_column(Text, nullable=True)
    side_photo: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_photo: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(back_populates="photoset")


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

class Generation(Base):
    __tablename__ = "generation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_date: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    account_id: Mapped[int] = mapped_column(ForeignKey("account.id"))
    bike_file_id: Mapped[int] = mapped_column(ForeignKey("bike_file.id"))
    helmet_file_id: Mapped[int | None] = mapped_column(ForeignKey("helmet_file.id"), nullable=True)
    jacket_file_id: Mapped[int | None] = mapped_column(ForeignKey("jacket_file.id"), nullable=True)
    glove_file_id: Mapped[int | None] = mapped_column(ForeignKey("glove_file.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending / success / failed

    user: Mapped["User"] = relationship(back_populates="generations")
    account: Mapped["Account"] = relationship()
    bike_file: Mapped["BikeFile"] = relationship(foreign_keys=[bike_file_id])
    helmet_file: Mapped["HelmetFile | None"] = relationship(foreign_keys=[helmet_file_id])
    jacket_file: Mapped["JacketFile | None"] = relationship(foreign_keys=[jacket_file_id])
    glove_file: Mapped["GloveFile | None"] = relationship(foreign_keys=[glove_file_id])


# ---------------------------------------------------------------------------
# DictionaryPrompt
# ---------------------------------------------------------------------------

class DictionaryPrompt(Base):
    __tablename__ = "dictionary_prompt"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(10))   # default / helmet / jacket / boots
    text: Mapped[str] = mapped_column(Text)


# ---------------------------------------------------------------------------
# Collage
# ---------------------------------------------------------------------------

class Collage(Base):
    __tablename__ = "collage"
    __table_args__ = (
        UniqueConstraint("type", "brand", name="uq_collage_type_brand"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[str] = mapped_column(String(20))   # helmet / jacket / boots
    brand: Mapped[str] = mapped_column(String(50))
    models_count: Mapped[int] = mapped_column(Integer)
    file: Mapped[str] = mapped_column(Text)
