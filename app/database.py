import sqlite3
import os
import shutil
from datetime import date, datetime
from typing import List, Optional, Tuple
from contextlib import contextmanager

from .models import Patient, Visit, Photo, Note, DATA_DIR


@contextmanager
def get_db():
    db_path = os.path.join(DATA_DIR, 'clinic.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


class Database:
    @staticmethod
    def init():
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS patients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT,
                    age INTEGER,
                    gender TEXT,
                    treatment_plan TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS visits (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_id INTEGER NOT NULL,
                    visit_date DATE NOT NULL,
                    stage_code TEXT DEFAULT 'month1',
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS photos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    visit_id INTEGER NOT NULL,
                    position_code TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    taken_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    imported INTEGER DEFAULT 0,
                    FOREIGN KEY (visit_id) REFERENCES visits(id) ON DELETE CASCADE
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    photo_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    x REAL DEFAULT 0,
                    y REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (photo_id) REFERENCES photos(id) ON DELETE CASCADE
                )
            ''')

    @staticmethod
    def add_patient(patient: Patient) -> int:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO patients (name, phone, age, gender, treatment_plan)
                VALUES (?, ?, ?, ?, ?)
            ''', (patient.name, patient.phone, patient.age, patient.gender, patient.treatment_plan))
            return c.lastrowid

    @staticmethod
    def get_patient(patient_id: int) -> Optional[Patient]:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM patients WHERE id = ?', (patient_id,))
            row = c.fetchone()
            if row:
                return Patient(
                    id=row['id'],
                    name=row['name'],
                    phone=row['phone'],
                    age=row['age'],
                    gender=row['gender'],
                    treatment_plan=row['treatment_plan'],
                    created_at=datetime.fromisoformat(row['created_at'])
                )
        return None

    @staticmethod
    def get_all_patients() -> List[Patient]:
        patients = []
        with get_db() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM patients ORDER BY created_at DESC')
            for row in c.fetchall():
                patients.append(Patient(
                    id=row['id'],
                    name=row['name'],
                    phone=row['phone'],
                    age=row['age'],
                    gender=row['gender'],
                    treatment_plan=row['treatment_plan'],
                    created_at=datetime.fromisoformat(row['created_at'])
                ))
        return patients

    @staticmethod
    def get_today_visits(visit_date: Optional[date] = None) -> List[Tuple[Patient, Visit]]:
        if visit_date is None:
            visit_date = date.today()
        results = []
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                SELECT p.id as patient_id, p.name, p.phone, p.age, p.gender, p.treatment_plan, p.created_at as patient_created,
                       v.id as visit_id, v.visit_date, v.stage_code, v.notes, v.created_at as visit_created
                FROM patients p
                JOIN visits v ON p.id = v.patient_id
                WHERE v.visit_date = ?
                ORDER BY v.created_at DESC
            ''', (visit_date.isoformat(),))
            for row in c.fetchall():
                patient = Patient(
                    id=row['patient_id'],
                    name=row['name'],
                    phone=row['phone'],
                    age=row['age'],
                    gender=row['gender'],
                    treatment_plan=row['treatment_plan'],
                    created_at=datetime.fromisoformat(row['patient_created'])
                )
                visit = Visit(
                    id=row['visit_id'],
                    patient_id=row['patient_id'],
                    visit_date=date.fromisoformat(row['visit_date']),
                    stage_code=row['stage_code'],
                    notes=row['notes'],
                    created_at=datetime.fromisoformat(row['visit_created'])
                )
                results.append((patient, visit))
        return results

    @staticmethod
    def add_visit(visit: Visit) -> int:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO visits (patient_id, visit_date, stage_code, notes)
                VALUES (?, ?, ?, ?)
            ''', (visit.patient_id, visit.visit_date.isoformat(), visit.stage_code, visit.notes))
            return c.lastrowid

    @staticmethod
    def get_patient_visits(patient_id: int) -> List[Visit]:
        visits = []
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                SELECT * FROM visits WHERE patient_id = ? ORDER BY visit_date DESC
            ''', (patient_id,))
            for row in c.fetchall():
                visits.append(Visit(
                    id=row['id'],
                    patient_id=row['patient_id'],
                    visit_date=date.fromisoformat(row['visit_date']),
                    stage_code=row['stage_code'],
                    notes=row['notes'],
                    created_at=datetime.fromisoformat(row['created_at'])
                ))
        return visits

    @staticmethod
    def get_visit(visit_id: int) -> Optional[Visit]:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM visits WHERE id = ?', (visit_id,))
            row = c.fetchone()
            if row:
                return Visit(
                    id=row['id'],
                    patient_id=row['patient_id'],
                    visit_date=date.fromisoformat(row['visit_date']),
                    stage_code=row['stage_code'],
                    notes=row['notes'],
                    created_at=datetime.fromisoformat(row['created_at'])
                )
        return None

    @staticmethod
    def add_photo(photo: Photo) -> int:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO photos (visit_id, position_code, file_path, file_name, taken_at, imported)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                photo.visit_id,
                photo.position_code,
                photo.file_path,
                photo.file_name,
                photo.taken_at.isoformat(),
                1 if photo.imported else 0
            ))
            return c.lastrowid

    @staticmethod
    def get_visit_photos(visit_id: int) -> List[Photo]:
        photos = []
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                SELECT * FROM photos WHERE visit_id = ? ORDER BY id
            ''', (visit_id,))
            for row in c.fetchall():
                photos.append(Photo(
                    id=row['id'],
                    visit_id=row['visit_id'],
                    position_code=row['position_code'],
                    file_path=row['file_path'],
                    file_name=row['file_name'],
                    taken_at=datetime.fromisoformat(row['taken_at']),
                    imported=bool(row['imported'])
                ))
        return photos

    @staticmethod
    def get_photo(photo_id: int) -> Optional[Photo]:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM photos WHERE id = ?', (photo_id,))
            row = c.fetchone()
            if row:
                return Photo(
                    id=row['id'],
                    visit_id=row['visit_id'],
                    position_code=row['position_code'],
                    file_path=row['file_path'],
                    file_name=row['file_name'],
                    taken_at=datetime.fromisoformat(row['taken_at']),
                    imported=bool(row['imported'])
                )
        return None

    @staticmethod
    def delete_photo(photo_id: int) -> bool:
        with get_db() as conn:
            c = conn.cursor()
            photo = Database.get_photo(photo_id)
            if photo and os.path.exists(photo.file_path):
                os.remove(photo.file_path)
            c.execute('DELETE FROM photos WHERE id = ?', (photo_id,))
            return c.rowcount > 0

    @staticmethod
    def update_photo_position(photo_id: int, position_code: str) -> bool:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('UPDATE photos SET position_code = ? WHERE id = ?',
                      (position_code, photo_id))
            return c.rowcount > 0

    @staticmethod
    def add_note(note: Note) -> int:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO notes (photo_id, content, x, y)
                VALUES (?, ?, ?, ?)
            ''', (note.photo_id, note.content, note.x, note.y))
            return c.lastrowid

    @staticmethod
    def get_photo_notes(photo_id: int) -> List[Note]:
        notes = []
        with get_db() as conn:
            c = conn.cursor()
            c.execute('SELECT * FROM notes WHERE photo_id = ? ORDER BY created_at',
                      (photo_id,))
            for row in c.fetchall():
                notes.append(Note(
                    id=row['id'],
                    photo_id=row['photo_id'],
                    content=row['content'],
                    x=row['x'],
                    y=row['y'],
                    created_at=datetime.fromisoformat(row['created_at'])
                ))
        return notes

    @staticmethod
    def delete_note(note_id: int) -> bool:
        with get_db() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM notes WHERE id = ?', (note_id,))
            return c.rowcount > 0

    @staticmethod
    def copy_photo_to_visit(src_path: str, visit: Visit, patient: Patient, position_code: str) -> Optional[str]:
        visit_dir = visit.get_visit_dir(patient.name, patient.id)
        ext = os.path.splitext(src_path)[1]
        timestamp = datetime.now().strftime('%H%M%S')
        new_filename = f"{position_code}_{timestamp}{ext}"
        dest_path = os.path.join(visit_dir, new_filename)
        try:
            shutil.copy2(src_path, dest_path)
            return dest_path
        except Exception as e:
            print(f"Copy photo failed: {e}")
            return None
