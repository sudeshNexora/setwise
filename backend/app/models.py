from datetime import datetime

from sqlalchemy import (JSON, DateTime, Float, ForeignKey, Integer, String,
                        Text, UniqueConstraint)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# MySQL's TEXT caps at 65,535 bytes — a syllabus PDF's extracted text goes past
# that. LONGTEXT on MySQL, plain TEXT everywhere else, so the same models still
# run on Postgres and SQLite unchanged.
LongText = Text().with_variant(LONGTEXT, "mysql")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="faculty")  # faculty | student | admin
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    uploads: Mapped[list["Upload"]] = relationship(back_populates="owner")
    papers: Mapped[list["Paper"]] = relationship(back_populates="creator")


class Upload(Base):
    """A syllabus / study-material file plus the text extracted from it."""
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    subject: Mapped[str] = mapped_column(String(160))
    unit: Mapped[str | None] = mapped_column(String(160), nullable=True)
    extracted_text: Mapped[str] = mapped_column(LongText, default="")
    topics: Mapped[list] = mapped_column(JSON, default=list)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    owner: Mapped[User] = relationship(back_populates="uploads")


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(primary_key=True)
    creator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str] = mapped_column(String(255))
    institution: Mapped[str] = mapped_column(String(255), default="")
    subject: Mapped[str] = mapped_column(String(160))
    semester: Mapped[str | None] = mapped_column(String(60), nullable=True)
    total_marks: Mapped[int] = mapped_column(Integer, default=50)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=90)
    instructions: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft | published
    source_upload_ids: Mapped[list] = mapped_column(JSON, default=list)
    docx_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    creator: Mapped[User] = relationship(back_populates="papers")
    sections: Mapped[list["Section"]] = relationship(
        back_populates="paper", cascade="all, delete-orphan", order_by="Section.position"
    )


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(160))
    instruction: Mapped[str] = mapped_column(String(255), default="")
    position: Mapped[int] = mapped_column(Integer, default=0)

    paper: Mapped[Paper] = relationship(back_populates="sections")
    questions: Mapped[list["Question"]] = relationship(
        back_populates="section", cascade="all, delete-orphan", order_by="Question.position"
    )


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[int] = mapped_column(primary_key=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("sections.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(LongText)
    qtype: Mapped[str] = mapped_column(String(20), default="short")  # mcq|short|long|fill
    options: Mapped[list] = mapped_column(JSON, default=list)
    answer_key: Mapped[str] = mapped_column(LongText, default="")
    marks: Mapped[int] = mapped_column(Integer, default=2)
    difficulty: Mapped[str] = mapped_column(String(12), default="medium")
    topic: Mapped[str | None] = mapped_column(String(160), nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    edited_by_user: Mapped[int] = mapped_column(Integer, default=0)

    section: Mapped[Section] = relationship(back_populates="questions")


class AnswerScript(Base):
    """A student's submitted answers for one paper, with grading output."""
    __tablename__ = "answer_scripts"
    __table_args__ = (UniqueConstraint("paper_id", "student_id", name="uq_script"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"))
    student_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    graded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    answers: Mapped[list["Answer"]] = relationship(
        back_populates="script", cascade="all, delete-orphan"
    )


class Answer(Base):
    __tablename__ = "answers"

    id: Mapped[int] = mapped_column(primary_key=True)
    script_id: Mapped[int] = mapped_column(ForeignKey("answer_scripts.id", ondelete="CASCADE"))
    question_id: Mapped[int] = mapped_column(ForeignKey("questions.id"))
    response_text: Mapped[str] = mapped_column(LongText, default="")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    similarity: Mapped[float] = mapped_column(Float, default=0.0)
    keyword_coverage: Mapped[float] = mapped_column(Float, default=0.0)
    feedback: Mapped[str] = mapped_column(Text, default="")
    overridden: Mapped[int] = mapped_column(Integer, default=0)

    script: Mapped[AnswerScript] = relationship(back_populates="answers")
