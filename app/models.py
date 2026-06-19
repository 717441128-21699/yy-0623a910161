from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Optional, List
import os
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHOTO_DIR = os.path.join(BASE_DIR, 'photos')
DATA_DIR = os.path.join(BASE_DIR, 'data')
UNDO_DIR = os.path.join(DATA_DIR, 'undo_cache')

os.makedirs(PHOTO_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UNDO_DIR, exist_ok=True)

SHOOT_POSITIONS = [
    {'code': 'front', 'name': '正面', 'order': 1},
    {'code': 'side', 'name': '侧面', 'order': 2},
    {'code': 'intra_front', 'name': '口内正位', 'order': 3},
    {'code': 'bite_left', 'name': '左侧咬合', 'order': 4},
    {'code': 'bite_right', 'name': '右侧咬合', 'order': 5},
]

TREATMENT_STAGES = [
    {'code': 'initial', 'name': '初诊', 'order': 1},
    {'code': 'month1', 'name': '1个月', 'order': 2},
    {'code': 'month3', 'name': '3个月', 'order': 3},
    {'code': 'month6', 'name': '6个月', 'order': 4},
    {'code': 'month12', 'name': '12个月', 'order': 5},
    {'code': 'finish', 'name': '结束', 'order': 6},
]

PHOTO_STATUS_PENDING = 'pending'
PHOTO_STATUS_TAKEN = 'taken'
PHOTO_STATUS_MISSING = 'missing'
PHOTO_STATUS_SKIPPED = 'skipped'

PHOTO_STATUS_DISPLAY = {
    PHOTO_STATUS_PENDING: '待拍',
    PHOTO_STATUS_TAKEN: '已拍',
    PHOTO_STATUS_MISSING: '缺拍',
    PHOTO_STATUS_SKIPPED: '跳过',
}


@dataclass
class Patient:
    id: Optional[int] = None
    name: str = ''
    phone: str = ''
    medical_record_number: str = ''
    age: Optional[int] = None
    gender: str = ''
    treatment_plan: str = ''
    created_at: datetime = field(default_factory=datetime.now)

    def get_photo_dir(self) -> str:
        path = os.path.join(PHOTO_DIR, f"{self.id}_{self.name}")
        os.makedirs(path, exist_ok=True)
        return path

    def get_display_identifier(self) -> str:
        parts = []
        if self.medical_record_number:
            parts.append(f"病历号:{self.medical_record_number}")
        if self.phone:
            parts.append(f"电话:{self.phone[-4:] if len(self.phone) > 4 else self.phone}")
        return '  '.join(parts)


@dataclass
class Visit:
    id: Optional[int] = None
    patient_id: int = 0
    visit_date: date = field(default_factory=date.today)
    appointment_time: Optional[time] = None
    stage_code: str = 'month1'
    notes: str = ''
    created_at: datetime = field(default_factory=datetime.now)

    def get_visit_dir(self, patient_name: str, patient_id: int) -> str:
        path = os.path.join(PHOTO_DIR, f"{patient_id}_{patient_name}", self.visit_date.strftime('%Y%m%d'))
        os.makedirs(path, exist_ok=True)
        return path

    def get_appointment_display(self) -> str:
        if self.appointment_time:
            return self.appointment_time.strftime('%H:%M')
        return ''


@dataclass
class Photo:
    id: Optional[int] = None
    visit_id: int = 0
    position_code: str = ''
    file_path: str = ''
    file_name: str = ''
    status: str = PHOTO_STATUS_PENDING
    taken_at: datetime = field(default_factory=datetime.now)
    imported: bool = False

    def get_display_name(self) -> str:
        pos = next((p for p in SHOOT_POSITIONS if p['code'] == self.position_code), None)
        return pos['name'] if pos else self.position_code

    def get_status_display(self) -> str:
        return PHOTO_STATUS_DISPLAY.get(self.status, self.status)


@dataclass
class Note:
    id: Optional[int] = None
    photo_id: int = 0
    content: str = ''
    x: float = 0.0
    y: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class UndoAction:
    action_type: str
    position_code: str
    old_photo: Optional[Photo] = None
    new_photo: Optional[Photo] = None
    old_file_backup: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

    def cleanup(self):
        if self.old_file_backup and os.path.exists(self.old_file_backup):
            try:
                os.remove(self.old_file_backup)
            except:
                pass


def backup_photo_for_undo(photo: Photo) -> Optional[str]:
    if not photo or not photo.file_path or not os.path.exists(photo.file_path):
        return None
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup_name = f"undo_{photo.id}_{timestamp}{os.path.splitext(photo.file_path)[1]}"
    backup_path = os.path.join(UNDO_DIR, backup_name)
    try:
        shutil.copy2(photo.file_path, backup_path)
        return backup_path
    except Exception as e:
        print(f"Backup photo failed: {e}")
        return None


def restore_photo_from_backup(backup_path: str, dest_path: str) -> bool:
    if not backup_path or not os.path.exists(backup_path):
        return False
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(backup_path, dest_path)
        return True
    except Exception as e:
        print(f"Restore photo failed: {e}")
        return False
