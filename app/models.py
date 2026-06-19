from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PHOTO_DIR = os.path.join(BASE_DIR, 'photos')
DATA_DIR = os.path.join(BASE_DIR, 'data')

os.makedirs(PHOTO_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

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


@dataclass
class Patient:
    id: Optional[int] = None
    name: str = ''
    phone: str = ''
    age: Optional[int] = None
    gender: str = ''
    treatment_plan: str = ''
    created_at: datetime = field(default_factory=datetime.now)

    def get_photo_dir(self) -> str:
        path = os.path.join(PHOTO_DIR, f"{self.id}_{self.name}")
        os.makedirs(path, exist_ok=True)
        return path


@dataclass
class Visit:
    id: Optional[int] = None
    patient_id: int = 0
    visit_date: date = field(default_factory=date.today)
    stage_code: str = 'month1'
    notes: str = ''
    created_at: datetime = field(default_factory=datetime.now)

    def get_visit_dir(self, patient_name: str, patient_id: int) -> str:
        path = os.path.join(PHOTO_DIR, f"{patient_id}_{patient_name}", self.visit_date.strftime('%Y%m%d'))
        os.makedirs(path, exist_ok=True)
        return path


@dataclass
class Photo:
    id: Optional[int] = None
    visit_id: int = 0
    position_code: str = ''
    file_path: str = ''
    file_name: str = ''
    taken_at: datetime = field(default_factory=datetime.now)
    imported: bool = False

    def get_display_name(self) -> str:
        pos = next((p for p in SHOOT_POSITIONS if p['code'] == self.position_code), None)
        return pos['name'] if pos else self.position_code


@dataclass
class Note:
    id: Optional[int] = None
    photo_id: int = 0
    content: str = ''
    x: float = 0.0
    y: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)
