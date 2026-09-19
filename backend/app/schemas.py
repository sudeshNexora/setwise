from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    department: str | None = None

    class Config:
        from_attributes = True


class RegisterIn(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)
    role: str = "faculty"
    department: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UploadOut(BaseModel):
    id: int
    filename: str
    subject: str
    unit: str | None
    topics: list[str]
    word_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class SectionSpec(BaseModel):
    title: str
    instruction: str = ""
    qtype: str = "short"          # mcq | short | long | fill
    count: int = 5
    marks_each: int = 2


class GenerateIn(BaseModel):
    title: str
    institution: str = ""
    subject: str
    semester: str | None = None
    duration_minutes: int = 90
    instructions: str = ""
    upload_ids: list[int]
    sections: list[SectionSpec]
    difficulty_mix: dict[str, int] = {"easy": 35, "medium": 45, "hard": 20}


class QuestionOut(BaseModel):
    id: int
    text: str
    qtype: str
    options: list[str]
    answer_key: str
    marks: int
    difficulty: str
    topic: str | None
    position: int

    class Config:
        from_attributes = True


class QuestionUpdate(BaseModel):
    text: str | None = None
    options: list[str] | None = None
    answer_key: str | None = None
    marks: int | None = None
    difficulty: str | None = None
    position: int | None = None


class QuestionCreate(BaseModel):
    section_id: int
    text: str
    qtype: str = "short"
    options: list[str] = []
    answer_key: str = ""
    marks: int = 2
    difficulty: str = "medium"


class SectionOut(BaseModel):
    id: int
    title: str
    instruction: str
    position: int
    questions: list[QuestionOut]

    class Config:
        from_attributes = True


class PaperOut(BaseModel):
    id: int
    title: str
    institution: str
    subject: str
    semester: str | None
    total_marks: int
    duration_minutes: int
    instructions: str
    status: str
    created_at: datetime
    sections: list[SectionOut]

    class Config:
        from_attributes = True


class PaperSummary(BaseModel):
    id: int
    title: str
    subject: str
    semester: str | None
    total_marks: int
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class AnswerIn(BaseModel):
    question_id: int
    response_text: str


class SubmitScriptIn(BaseModel):
    paper_id: int
    answers: list[AnswerIn]


class AnswerResult(BaseModel):
    question_id: int
    score: float
    max_marks: int
    similarity: float
    keyword_coverage: float
    feedback: str


class ScriptResult(BaseModel):
    script_id: int
    total_score: float
    total_marks: int
    results: list[AnswerResult]
