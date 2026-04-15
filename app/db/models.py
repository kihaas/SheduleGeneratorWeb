from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Set
from datetime import datetime
import json


class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class TeacherBase(BaseModel):
    name: str


class TeacherCreate(TeacherBase):
    pass


class Teacher(TeacherBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


# app/db/models.py
class SubjectBase(BaseModel):
    teacher: str
    subject_name: str
    total_hours: int
    remaining_hours: int


class SubjectCreate(SubjectBase):
    pass


class Subject(SubjectBase):
    id: Optional[int] = None
    remaining_pairs: int = 0
    priority: int = 0
    max_per_day: int = 2
    min_per_week: int = 1
    max_per_week: int = 20

    class Config:
        from_attributes = True


class LessonBase(BaseModel):
    day: int
    time_slot: int
    teacher: str
    subject_name: str

class NegativeFilter(BaseModel):
    teacher: str
    restricted_days: List[int] = []
    restricted_slots: List[int] = []

    class Config:
        from_attributes = True


class LessonCreate(LessonBase):
    pass


class Lesson(LessonBase):
    id: Optional[int] = None
    editable: bool = True

    class Config:
        from_attributes = True


class NegativeFilterBase(BaseModel):
    teacher: str
    restricted_days: Set[int] = set()
    restricted_slots: Set[int] = set()


class NegativeFilterCreate(NegativeFilterBase):
    pass


class NegativeFilter(NegativeFilterBase):
    class Config:
        from_attributes = True


class SavedScheduleBase(BaseModel):
    name: str
    user_id: Optional[int] = None


class SavedScheduleCreate(SavedScheduleBase):
    pass


class SavedSchedule(SavedScheduleBase):
    id: int
    created_at: datetime
    payload: Dict

    class Config:
        from_attributes = True


class ScheduleData(BaseModel):
    subjects: List[Subject]
    lessons: List[Lesson]
    teachers: List[Teacher]
    negative_filters: Dict[str, NegativeFilter] = {}


class Statistics(BaseModel):
    total_subjects: int
    total_teachers: int
    total_hours: int
    remaining_hours: int
    scheduled_pairs: int
    remaining_pairs: int

# Модели для системы групп
class StudyGroupBase(BaseModel):
    name: str

class StudyGroupCreate(StudyGroupBase):
    pass

class StudyGroup(StudyGroupBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True