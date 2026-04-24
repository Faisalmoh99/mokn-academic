"""Data access layer. Session 2 is JSON-backed; Session 5 swaps to Firestore."""
from mokn.data.repository import (
    CourseNotFound,
    CourseRepository,
    StudentNotFound,
    StudentRepository,
    get_course_repository,
    get_student_repository,
)

__all__ = [
    "CourseNotFound",
    "CourseRepository",
    "StudentNotFound",
    "StudentRepository",
    "get_course_repository",
    "get_student_repository",
]
