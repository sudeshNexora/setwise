"""Create a demo faculty account and a sample study-material upload."""
from app.database import Base, SessionLocal, engine
from app.models import Upload, User
from app.security import hash_password
from app.services.topics import extract_topics

SAMPLE = """
A linked list is a linear data structure in which elements are stored in nodes and
each node holds a reference to the next node. Unlike an array, a linked list does not
store elements in contiguous memory, so insertion and deletion at a known position
take constant time while random access takes linear time.

A stack is a linear data structure that follows the last in first out principle.
The two primary operations on a stack are push, which adds an element to the top,
and pop, which removes the element at the top. The function call stack used during
recursive execution is a direct application of this structure.

A queue is a linear data structure that follows the first in first out principle.
Elements are inserted at the rear through an enqueue operation and removed from the
front through a dequeue operation. A circular queue reuses the space freed at the
front, which avoids the false overflow that a simple linear queue suffers from.

Recursion is a technique in which a function calls itself on a smaller input until it
reaches a base case. Every recursive solution has an equivalent iterative solution
that uses an explicit stack, and the choice between them is usually a trade-off
between readability and memory used by the call stack.
"""


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    if db.query(User).filter(User.email == "faculty@college.edu").first():
        print("Demo data already present.")
        return

    faculty = User(
        name="R. Sharma", email="faculty@college.edu",
        password_hash=hash_password("setwise123"),
        role="faculty", department="Computer Science",
    )
    student = User(
        name="A. Nair", email="student@college.edu",
        password_hash=hash_password("setwise123"), role="student",
    )
    db.add_all([faculty, student])
    db.flush()

    db.add(Upload(
        owner_id=faculty.id, filename="unit2-linear-structures.txt",
        stored_path="(seeded)", subject="Data Structures",
        unit="Unit 2 - Linear Structures", extracted_text=SAMPLE.strip(),
        topics=extract_topics(SAMPLE), word_count=len(SAMPLE.split()),
    ))
    db.commit()
    print("Seeded. Faculty: faculty@college.edu / setwise123")
    print("        Student: student@college.edu / setwise123")


if __name__ == "__main__":
    main()
