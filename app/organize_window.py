import os
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QDialog, QScrollArea, QFrame, QFileDialog,
    QGraphicsDropShadowEffect, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QMimeData
from PySide6.QtGui import QPixmap, QFont, QPainter, QColor, QBrush, QDrag, QPen

from .database import Database
from .models import (
    Patient, Visit, Photo, Note, UndoAction,
    SHOOT_POSITIONS, TREATMENT_STAGES,
    backup_photo_for_undo, restore_photo_from_backup,
    PHOTO_STATUS_TAKEN, PHOTO_STATUS_PENDING, PHOTO_STATUS_MISSING, PHOTO_STATUS_SKIPPED,
    PHOTO_STATUS_DISPLAY
)


class PhotoSlot(QFrame):
    photo_dropped = Signal(str, str)
    photo_removed = Signal(int)

    def __init__(self, position_code: str, position_name: str, photo: Photo = None, parent=None):
        super().__init__(parent)
        self.position_code = position_code
        self.position_name = position_name
        self.photo = photo
        self.setAcceptDrops(True)
        self.setFixedSize(180, 180)
        self._init_ui()
        self._update_content()

    def _init_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(8, 8, 8, 8)
        self.layout.setSpacing(4)

        self.name_label = QLabel(self.position_name)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet('font-weight: bold; color: #1565c0; font-size: 13px;')
        self.layout.addWidget(self.name_label)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(150, 110)
        self.image_label.setStyleSheet('''
            QLabel {
                border: 2px dashed #bdbdbd;
                border-radius: 6px;
                background: #fafafa;
                color: #9e9e9e;
            }
        ''')
        self.layout.addWidget(self.image_label, 1)

        self.status_label = QLabel('拖入照片')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet('color: #9e9e9e; font-size: 11px;')
        self.layout.addWidget(self.status_label)

        self.setStyleSheet('''
            PhotoSlot {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            PhotoSlot:hover {
                border-color: #1976d2;
            }
        ''')

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(4)
        shadow.setXOffset(0)
        shadow.setYOffset(2)
        shadow.setColor(QColor(0, 0, 0, 20))
        self.setGraphicsEffect(shadow)

    def _update_content(self):
        has_real_photo = (self.photo and self.photo.status == PHOTO_STATUS_TAKEN 
                         and self.photo.file_path and os.path.exists(self.photo.file_path))
        
        if has_real_photo:
            pixmap = QPixmap(self.photo.file_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    self.image_label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.image_label.setPixmap(scaled)
                self.image_label.setStyleSheet('''
                    QLabel {
                        border: 2px solid #4caf50;
                        border-radius: 6px;
                        background: #f1f8e9;
                    }
                ''')
                self.status_label.setText('✓ 已放置')
                self.status_label.setStyleSheet('color: #4caf50; font-size: 11px; font-weight: bold;')
                return

        status_text = '拖入照片'
        status_color = '#9e9e9e'
        border_color = '#bdbdbd'
        bg_color = '#fafafa'
        icon_text = '+'

        if self.photo:
            if self.photo.status == PHOTO_STATUS_MISSING:
                status_text = '⚠ 缺拍'
                status_color = '#e53935'
                border_color = '#ef9a9a'
                bg_color = '#ffebee'
                icon_text = '⚠'
            elif self.photo.status == PHOTO_STATUS_SKIPPED:
                status_text = '⏭ 跳过'
                status_color = '#f9a825'
                border_color = '#ffe082'
                bg_color = '#fffde7'
                icon_text = '⏭'
            elif self.photo.status == PHOTO_STATUS_PENDING:
                status_text = '待拍'
                status_color = '#666'
                icon_text = '○'

        self.image_label.setText(icon_text)
        self.image_label.setStyleSheet(f'''
            QLabel {{
                border: 2px dashed {border_color};
                border-radius: 6px;
                background: {bg_color};
                color: {status_color};
                font-size: 28px;
            }}
        ''')
        self.status_label.setText(status_text)
        self.status_label.setStyleSheet(f'color: {status_color}; font-size: 11px; font-weight: bold;')

    def has_real_photo(self) -> bool:
        return (self.photo and self.photo.status == PHOTO_STATUS_TAKEN 
                and self.photo.file_path and os.path.exists(self.photo.file_path))

    def is_empty_slot(self) -> bool:
        return not self.has_real_photo()

    def set_photo(self, photo: Photo):
        self.photo = photo
        self._update_content()

    def clear_photo(self):
        self.photo = None
        self._update_content()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self.setStyleSheet('''
                PhotoSlot {
                    background: #e3f2fd;
                    border: 2px solid #1976d2;
                    border-radius: 8px;
                }
            ''')

    def dragLeaveEvent(self, event):
        self.setStyleSheet('''
            PhotoSlot {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            PhotoSlot:hover {
                border-color: #1976d2;
            }
        ''')

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if urls:
                file_path = urls[0].toLocalFile()
                if file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    self.photo_dropped.emit(self.position_code, file_path)
                else:
                    QMessageBox.warning(self, '提示', '请拖入图片文件（JPG, PNG, BMP）')

        self.setStyleSheet('''
            PhotoSlot {
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            PhotoSlot:hover {
                border-color: #1976d2;
            }
        ''')

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.photo:
            self.setCursor(Qt.ClosedHandCursor)

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.ArrowCursor)

    def contextMenuEvent(self, event):
        if self.photo:
            reply = QMessageBox.question(
                self, '撤回照片',
                f'确定要撤回「{self.position_name}」的照片吗？',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.photo_removed.emit(self.photo.id)


class OrganizeWindow(QDialog):
    organize_finished = Signal()

    def __init__(self, patient_id: int, visit_id: int, parent=None):
        super().__init__(parent)
        self.patient_id = patient_id
        self.visit_id = visit_id
        self.patient = Database.get_patient(patient_id)
        self.visit = Database.get_visit(visit_id)
        self.photo_slots = {}
        self.undo_stack = []

        self.setWindowTitle(f'照片归位 - {self.patient.name}')
        self.resize(1100, 750)
        self.setModal(True)

        self._init_ui()
        self._load_photos()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        header_layout = QHBoxLayout()

        stage_name = next(
            (s['name'] for s in TREATMENT_STAGES if s['code'] == self.visit.stage_code),
            self.visit.stage_code
        )
        patient_info = QLabel(f'患者：{self.patient.name}  |  疗程：{stage_name}  |  日期：{self.visit.visit_date}')
        patient_info.setStyleSheet('font-size: 14px; color: #333;')
        header_layout.addWidget(patient_info)
        header_layout.addStretch()

        self.import_btn = QPushButton('📁  从文件夹导入')
        self.import_btn.setStyleSheet('''
            QPushButton {
                background: #1976d2;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background: #1565c0; }
        ''')
        self.import_btn.clicked.connect(self._import_photos)
        header_layout.addWidget(self.import_btn)

        self.undo_btn = QPushButton('↶  撤回')
        self.undo_btn.setStyleSheet('''
            QPushButton {
                background: #ff9800;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background: #f57c00; }
            QPushButton:disabled {
                background: #ccc;
            }
        ''')
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self._undo_last)
        header_layout.addWidget(self.undo_btn)

        close_btn = QPushButton('关闭')
        close_btn.setStyleSheet('''
            QPushButton {
                background: #757575;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background: #616161; }
        ''')
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)

        layout.addLayout(header_layout)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('''
            QScrollArea {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background: #f5f5f5;
            }
        ''')

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(20)

        stage_label = QLabel('拍摄位格子 - 拖入照片到对应位置')
        stage_label.setFont(QFont('Arial', 12, QFont.Bold))
        stage_label.setStyleSheet('color: #424242;')
        content_layout.addWidget(stage_label)

        grid_layout = QHBoxLayout()
        grid_layout.setSpacing(15)

        for pos in SHOOT_POSITIONS:
            slot = PhotoSlot(pos['code'], pos['name'])
            slot.photo_dropped.connect(self._on_photo_dropped)
            slot.photo_removed.connect(self._on_photo_removed)
            self.photo_slots[pos['code']] = slot
            grid_layout.addWidget(slot)

        grid_layout.addStretch()
        content_layout.addLayout(grid_layout)

        tips = QLabel('💡 使用说明：从资源管理器拖入照片到对应格子，或点击「从文件夹导入」选择照片。右键已放置的照片可撤回。')
        tips.setStyleSheet('color: #757575; padding: 10px; background: #fff8e1; border-radius: 6px;')
        tips.setWordWrap(True)
        content_layout.addWidget(tips)

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        self.status_label = QLabel('等待归位照片...')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet('color: #666; padding-top: 8px;')
        layout.addWidget(self.status_label)

    def _load_photos(self):
        photos = Database.get_visit_photos(self.visit_id)
        photo_by_position = {p.position_code: p for p in photos}

        for pos in SHOOT_POSITIONS:
            slot = self.photo_slots[pos['code']]
            if pos['code'] in photo_by_position:
                slot.set_photo(photo_by_position[pos['code']])

        self._update_status()

    def _on_photo_dropped(self, position_code: str, file_path: str):
        dest_path = Database.copy_photo_to_visit(
            file_path, self.visit, self.patient, position_code
        )

        if not dest_path:
            QMessageBox.critical(self, '错误', '照片复制失败，请检查文件权限')
            return

        old_photo = None
        old_file_backup = None
        slot = self.photo_slots[position_code]
        if slot.photo:
            old_photo = slot.photo
            if slot.has_real_photo():
                old_file_backup = backup_photo_for_undo(old_photo)
            Database.delete_photo(slot.photo.id)

        photo = Photo(
            visit_id=self.visit_id,
            position_code=position_code,
            file_path=dest_path,
            file_name=os.path.basename(dest_path),
            status=PHOTO_STATUS_TAKEN,
            taken_at=datetime.now(),
            imported=True
        )
        photo_id = Database.add_photo(photo)
        photo.id = photo_id

        undo_action = UndoAction(
            action_type='replace' if old_photo else 'add',
            position_code=position_code,
            old_photo=old_photo,
            new_photo=photo,
            old_file_backup=old_file_backup
        )
        self.undo_stack.append(undo_action)
        self.undo_btn.setEnabled(True)

        slot.set_photo(photo)
        self._update_status()

        pos_name = next((p['name'] for p in SHOOT_POSITIONS if p['code'] == position_code), position_code)
        self.status_label.setText(f'✓ 已放置 {pos_name}')

    def _on_photo_removed(self, photo_id: int):
        photo = Database.get_photo(photo_id)
        if not photo:
            return

        position_code = photo.position_code
        old_file_backup = backup_photo_for_undo(photo)
        Database.delete_photo(photo_id)

        undo_action = UndoAction(
            action_type='remove',
            position_code=position_code,
            old_photo=photo,
            new_photo=None,
            old_file_backup=old_file_backup
        )
        self.undo_stack.append(undo_action)
        self.undo_btn.setEnabled(True)

        slot = self.photo_slots[position_code]
        slot.clear_photo()
        self._update_status()

    def _undo_last(self):
        if not self.undo_stack:
            return

        undo_action = self.undo_stack.pop()
        slot = self.photo_slots[undo_action.position_code]

        if undo_action.action_type in ('add', 'replace'):
            if undo_action.new_photo:
                Database.delete_photo(undo_action.new_photo.id)

            if undo_action.old_photo:
                if undo_action.old_file_backup:
                    restore_photo_from_backup(
                        undo_action.old_file_backup,
                        undo_action.old_photo.file_path
                    )
                old_photo_copy = Photo(
                    id=None,
                    visit_id=undo_action.old_photo.visit_id,
                    position_code=undo_action.old_photo.position_code,
                    file_path=undo_action.old_photo.file_path,
                    file_name=undo_action.old_photo.file_name,
                    status=undo_action.old_photo.status,
                    taken_at=undo_action.old_photo.taken_at,
                    imported=undo_action.old_photo.imported
                )
                new_id = Database.add_photo(old_photo_copy)
                old_photo_copy.id = new_id
                slot.set_photo(old_photo_copy)
            else:
                slot.clear_photo()

        elif undo_action.action_type == 'remove':
            if undo_action.old_photo:
                if undo_action.old_file_backup:
                    restore_photo_from_backup(
                        undo_action.old_file_backup,
                        undo_action.old_photo.file_path
                    )
                old_photo_copy = Photo(
                    id=None,
                    visit_id=undo_action.old_photo.visit_id,
                    position_code=undo_action.old_photo.position_code,
                    file_path=undo_action.old_photo.file_path,
                    file_name=undo_action.old_photo.file_name,
                    status=undo_action.old_photo.status,
                    taken_at=undo_action.old_photo.taken_at,
                    imported=undo_action.old_photo.imported
                )
                new_id = Database.add_photo(old_photo_copy)
                old_photo_copy.id = new_id
                slot.set_photo(old_photo_copy)

        undo_action.cleanup()

        if not self.undo_stack:
            self.undo_btn.setEnabled(False)

        self._update_status()
        self.status_label.setText('↶ 已撤回上一步操作')

    def _import_photos(self):
        file_dialog = QFileDialog()
        file_paths, _ = file_dialog.getOpenFileNames(
            self,
            '选择要导入的照片',
            '',
            '图片文件 (*.jpg *.jpeg *.png *.bmp)'
        )

        if not file_paths:
            return

        empty_positions = [
            pos['code'] for pos in SHOOT_POSITIONS
            if self.photo_slots[pos['code']].is_empty_slot()
        ]

        if not empty_positions:
            QMessageBox.information(self, '提示', '所有拍摄位都已有照片')
            return

        import_count = min(len(file_paths), len(empty_positions))

        for i in range(import_count):
            position_code = empty_positions[i]
            file_path = file_paths[i]

            dest_path = Database.copy_photo_to_visit(
                file_path, self.visit, self.patient, position_code
            )

            if dest_path:
                old_photo = None
                old_file_backup = None
                slot = self.photo_slots[position_code]
                if slot.photo:
                    old_photo = slot.photo
                    if slot.has_real_photo():
                        old_file_backup = backup_photo_for_undo(old_photo)
                    Database.delete_photo(slot.photo.id)

                photo = Photo(
                    visit_id=self.visit_id,
                    position_code=position_code,
                    file_path=dest_path,
                    file_name=os.path.basename(dest_path),
                    status=PHOTO_STATUS_TAKEN,
                    taken_at=datetime.now(),
                    imported=True
                )
                photo_id = Database.add_photo(photo)
                photo.id = photo_id

                undo_action = UndoAction(
                    action_type='replace' if old_photo else 'add',
                    position_code=position_code,
                    old_photo=old_photo,
                    new_photo=photo,
                    old_file_backup=old_file_backup
                )
                self.undo_stack.append(undo_action)
                self.photo_slots[position_code].set_photo(photo)

        if import_count > 0:
            self.undo_btn.setEnabled(True)
            self._update_status()
            self.status_label.setText(f'✓ 已导入 {import_count} 张照片')

    def _update_status(self):
        filled = sum(1 for slot in self.photo_slots.values() if slot.has_real_photo())
        total = len(self.photo_slots)
        missing = sum(1 for slot in self.photo_slots.values() 
                     if slot.photo and slot.photo.status == PHOTO_STATUS_MISSING)
        skipped = sum(1 for slot in self.photo_slots.values() 
                     if slot.photo and slot.photo.status == PHOTO_STATUS_SKIPPED)
        status_text = f'已归位 {filled}/{total} 张'
        if missing > 0:
            status_text += f'  |  缺拍 {missing}'
        if skipped > 0:
            status_text += f'  |  跳过 {skipped}'
        self.status_label.setText(status_text)

    def closeEvent(self, event):
        self.organize_finished.emit()
        super().closeEvent(event)
