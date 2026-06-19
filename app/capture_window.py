import cv2
import os
import shutil
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QMessageBox, QDialog, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QImage, QPixmap, QFont, QPainter, QColor, QPen, QBrush

from .database import Database
from .models import (
    Patient, Visit, Photo, SHOOT_POSITIONS, TREATMENT_STAGES,
    PHOTO_STATUS_PENDING, PHOTO_STATUS_TAKEN, PHOTO_STATUS_MISSING, PHOTO_STATUS_SKIPPED,
    PHOTO_STATUS_DISPLAY
)


class PositionStatusWidget(QFrame):
    clicked = Signal(int)

    def __init__(self, position, index, parent=None):
        super().__init__(parent)
        self.position = position
        self.index = index
        self.status = PHOTO_STATUS_PENDING
        self.selected = False
        self.setFixedSize(90, 70)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

    def set_status(self, status):
        self.status = status
        self.update()

    def set_selected(self, selected):
        self.selected = selected
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(2, 2, -2, -2)

        if self.selected:
            painter.setPen(QPen(QColor('#1976d2'), 3))
        else:
            painter.setPen(QPen(QColor('#e0e0e0'), 1))

        status_colors = {
            PHOTO_STATUS_PENDING: '#f5f5f5',
            PHOTO_STATUS_TAKEN: '#c8e6c9',
            PHOTO_STATUS_MISSING: '#ffcdd2',
            PHOTO_STATUS_SKIPPED: '#fff9c4',
        }
        painter.setBrush(QBrush(QColor(status_colors.get(self.status, '#f5f5f5'))))
        painter.drawRoundedRect(rect, 6, 6)

        painter.setPen(QPen(QColor('#333')))
        font = QFont()
        font.setBold(True)
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignHCenter | Qt.AlignTop, self.position['name'])

        status_text = PHOTO_STATUS_DISPLAY.get(self.status, '')
        font.setBold(False)
        font.setPointSize(9)
        painter.setFont(font)

        status_text_colors = {
            PHOTO_STATUS_PENDING: '#999',
            PHOTO_STATUS_TAKEN: '#2e7d32',
            PHOTO_STATUS_MISSING: '#c62828',
            PHOTO_STATUS_SKIPPED: '#f57f17',
        }
        painter.setPen(QPen(QColor(status_text_colors.get(self.status, '#666'))))
        painter.drawText(rect, Qt.AlignHCenter | Qt.AlignBottom, status_text)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.index)


class CaptureWindow(QDialog):
    capture_finished = Signal()

    def __init__(self, patient_id: int, visit_id: int, parent=None):
        super().__init__(parent)
        self.patient_id = patient_id
        self.visit_id = visit_id
        self.patient = Database.get_patient(patient_id)
        self.visit = Database.get_visit(visit_id)

        self.current_position_index = 0
        self.position_statuses = {}
        self.position_photos = {}
        self.camera = None
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_frame)

        self.setWindowTitle(f'拍照采集 - {self.patient.name}')
        self.resize(1050, 820)
        self.setModal(True)

        self._load_existing_photos()
        self._init_ui()
        self._start_camera()

    def _load_existing_photos(self):
        photos = Database.get_visit_photos_by_position(self.visit_id)
        for pos in SHOOT_POSITIONS:
            if pos['code'] in photos:
                photo = photos[pos['code']]
                self.position_photos[pos['code']] = photo
                self.position_statuses[pos['code']] = photo.status if photo.status else PHOTO_STATUS_TAKEN
            else:
                self.position_statuses[pos['code']] = PHOTO_STATUS_PENDING

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header_layout = QHBoxLayout()

        stage_name = next(
            (s['name'] for s in TREATMENT_STAGES if s['code'] == self.visit.stage_code),
            self.visit.stage_code
        )
        identifier = self.patient.get_display_identifier()
        patient_text = f'患者：{self.patient.name}'
        if identifier:
            patient_text += f'  ({identifier})'
        patient_text += f'  |  疗程：{stage_name}  |  {self.visit.visit_date}'
        patient_info = QLabel(patient_text)
        patient_info.setStyleSheet('font-size: 13px; color: #333;')
        header_layout.addWidget(patient_info)
        header_layout.addStretch()

        close_btn = QPushButton('关闭')
        close_btn.setFixedWidth(80)
        close_btn.setStyleSheet('''
            QPushButton {
                background: #757575;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background: #616161; }
        ''')
        close_btn.clicked.connect(self.close)
        header_layout.addWidget(close_btn)

        layout.addLayout(header_layout)

        self.status_bar = QHBoxLayout()
        self.status_bar.setSpacing(6)
        self.position_widgets = {}
        for i, pos in enumerate(SHOOT_POSITIONS):
            widget = PositionStatusWidget(pos, i)
            widget.clicked.connect(self._on_position_clicked)
            widget.set_status(self.position_statuses.get(pos['code'], PHOTO_STATUS_PENDING))
            if i == 0:
                widget.set_selected(True)
            self.position_widgets[pos['code']] = widget
            self.status_bar.addWidget(widget)
        self.status_bar.addStretch()
        layout.addLayout(self.status_bar)

        progress_layout = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(len(SHOOT_POSITIONS))
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet('''
            QProgressBar {
                border: 1px solid #bdbdbd;
                border-radius: 6px;
                text-align: center;
                height: 22px;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background: #4caf50;
                border-radius: 6px;
            }
        ''')
        progress_layout.addWidget(self.progress_bar, 1)

        self.count_label = QLabel()
        self.count_label.setStyleSheet('font-size: 13px; color: #666; padding-left: 10px;')
        progress_layout.addWidget(self.count_label)
        layout.addLayout(progress_layout)

        self.position_label = QLabel(self._get_current_position_text())
        self.position_label.setAlignment(Qt.AlignCenter)
        position_font = QFont()
        position_font.setPointSize(20)
        position_font.setBold(True)
        self.position_label.setFont(position_font)
        self.position_label.setStyleSheet('color: #1565c0;')
        layout.addWidget(self.position_label)

        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet('background: #000; border-radius: 8px;')
        self.video_label.setMinimumHeight(380)
        layout.addWidget(self.video_label, 1)

        btn_row1 = QHBoxLayout()
        btn_row1.setSpacing(10)

        self.skip_btn = QPushButton('⏭  跳过 (S)')
        self._style_action_button(self.skip_btn, '#ffb300', '#f57c00')
        self.skip_btn.clicked.connect(self._skip_position)
        btn_row1.addWidget(self.skip_btn, 1)

        self.missing_btn = QPushButton('⚠  标记缺拍 (M)')
        self._style_action_button(self.missing_btn, '#e57373', '#c62828')
        self.missing_btn.clicked.connect(self._mark_missing)
        btn_row1.addWidget(self.missing_btn, 1)

        self.retake_btn = QPushButton('🔄  复拍覆盖 (R)')
        self._style_action_button(self.retake_btn, '#64b5f6', '#1976d2')
        self.retake_btn.clicked.connect(self._retake_photo)
        btn_row1.addWidget(self.retake_btn, 1)
        self._update_retake_button()

        layout.addLayout(btn_row1)

        btn_row2 = QHBoxLayout()
        btn_row2.setSpacing(12)

        self.prev_btn = QPushButton('← 上一张 (←)')
        self._style_nav_button(self.prev_btn, '#78909c')
        self.prev_btn.clicked.connect(self._prev_position)
        self.prev_btn.setEnabled(False)
        btn_row2.addWidget(self.prev_btn)

        self.capture_btn = QPushButton('📸  拍照 (空格键)')
        self.capture_btn.setMinimumHeight(65)
        self.capture_btn.setStyleSheet('''
            QPushButton {
                background: #e53935;
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 20px;
                font-weight: bold;
            }
            QPushButton:hover { background: #d32f2f; }
        ''')
        self.capture_btn.clicked.connect(self._capture_photo)
        btn_row2.addWidget(self.capture_btn, 2)

        self.next_btn = QPushButton('下一张 → (→)')
        self._style_nav_button(self.next_btn, '#78909c')
        self.next_btn.clicked.connect(self._next_position)
        btn_row2.addWidget(self.next_btn)

        layout.addLayout(btn_row2)

        tips = QLabel('快捷键：空格=拍照 | R=复拍 | S=跳过 | M=缺拍 | ←→=切换 | 点击上方小图跳转')
        tips.setAlignment(Qt.AlignCenter)
        tips.setStyleSheet('color: #999; font-size: 11px; padding-top: 4px;')
        layout.addWidget(tips)

        self._update_progress()
        self._update_retake_button()

    def _style_action_button(self, btn, color, dark_color):
        btn.setMinimumHeight(45)
        btn.setStyleSheet(f'''
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {dark_color};
            }}
            QPushButton:disabled {{
                background: #ccc;
            }}
        ''')

    def _style_nav_button(self, btn, color):
        btn.setMinimumHeight(65)
        btn.setStyleSheet(f'''
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 15px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {self._darken_color(color)};
            }}
            QPushButton:disabled {{
                background: #ccc;
            }}
        ''')

    def _darken_color(self, hex_color):
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        factor = 0.85
        return f'#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}'

    def _get_current_position_text(self) -> str:
        pos = SHOOT_POSITIONS[self.current_position_index]
        status = self.position_statuses.get(pos['code'], PHOTO_STATUS_PENDING)
        status_text = PHOTO_STATUS_DISPLAY.get(status, '')
        return f'第 {pos["order"]}/{len(SHOOT_POSITIONS)} 张：{pos["name"]}  ({status_text})'

    def _start_camera(self):
        self.camera = cv2.VideoCapture(0)
        if not self.camera.isOpened():
            self.camera = cv2.VideoCapture(1)
        if not self.camera.isOpened():
            QMessageBox.warning(self, '错误', '无法打开摄像头，请检查设备连接')
            self.close()
            return

        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.timer.start(30)

    def _update_frame(self):
        if self.camera is None:
            return

        ret, frame = self.camera.read()
        if ret:
            frame = cv2.flip(frame, 1)
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            height, width, channel = frame_rgb.shape
            bytes_per_line = channel * width
            qt_image = QImage(frame_rgb.data, width, height, bytes_per_line, QImage.Format_RGB888)

            pixmap = QPixmap.fromImage(qt_image)
            scaled_pixmap = pixmap.scaled(
                self.video_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            pos = SHOOT_POSITIONS[self.current_position_index]
            painter = QPainter(scaled_pixmap)
            painter.setRenderHint(QPainter.Antialiasing)

            overlay_color = QColor(0, 0, 0, 100)
            painter.fillRect(0, 0, scaled_pixmap.width(), 50, overlay_color)

            text_pen = QPen(QColor(255, 255, 255))
            painter.setPen(text_pen)
            font = QFont()
            font.setPointSize(15)
            font.setBold(True)
            painter.setFont(font)

            status = self.position_statuses.get(pos['code'], PHOTO_STATUS_PENDING)
            status_text = PHOTO_STATUS_DISPLAY.get(status, '')

            status_colors = {
                PHOTO_STATUS_PENDING: QColor('#cccccc'),
                PHOTO_STATUS_TAKEN: QColor('#76ff03'),
                PHOTO_STATUS_MISSING: QColor('#ff5252'),
                PHOTO_STATUS_SKIPPED: QColor('#ffee58'),
            }

            painter.drawText(20, 35, f'{pos["order"]}. {pos["name"]}')

            painter.setPen(QPen(status_colors.get(status, QColor('#ccc'))))
            painter.drawText(scaled_pixmap.width() - 120, 35, status_text)

            if status == PHOTO_STATUS_TAKEN:
                pos_code = pos['code']
                if pos_code in self.position_photos and self.position_photos[pos_code].file_path:
                    small_pixmap = QPixmap(self.position_photos[pos_code].file_path)
                    if not small_pixmap.isNull():
                        thumb_size = QSize(100, 75)
                        thumb = small_pixmap.scaled(thumb_size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        x = scaled_pixmap.width() - thumb.width() - 10
                        y = 60
                        painter.drawPixmap(x, y, thumb)
                        painter.setPen(QPen(QColor(255, 255, 255)))
                        painter.setBrush(Qt.NoBrush)
                        painter.drawRect(x - 1, y - 1, thumb.width() + 2, thumb.height() + 2)

            painter.end()
            self.video_label.setPixmap(scaled_pixmap)

    def _on_position_clicked(self, index):
        self._jump_to_position(index)

    def _jump_to_position(self, index):
        old_pos = SHOOT_POSITIONS[self.current_position_index]
        self.position_widgets[old_pos['code']].set_selected(False)

        self.current_position_index = index
        new_pos = SHOOT_POSITIONS[self.current_position_index]
        self.position_widgets[new_pos['code']].set_selected(True)

        self._update_position()

    def _capture_photo(self):
        if self.camera is None:
            return

        ret, frame = self.camera.read()
        if not ret:
            QMessageBox.warning(self, '错误', '拍照失败，请重试')
            return

        self._save_photo(frame, PHOTO_STATUS_TAKEN)

    def _retake_photo(self):
        pos = SHOOT_POSITIONS[self.current_position_index]
        if pos['code'] not in self.position_photos:
            QMessageBox.information(self, '提示', '该位置还没有照片，不需要复拍')
            return

        reply = QMessageBox.question(
            self, '确认复拍',
            f'确定要覆盖「{pos["name"]}」的现有照片吗？',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        if self.camera is None:
            return

        ret, frame = self.camera.read()
        if not ret:
            QMessageBox.warning(self, '错误', '拍照失败，请重试')
            return

        old_photo = self.position_photos[pos['code']]
        if old_photo.id:
            Database.delete_photo(old_photo.id, delete_file=True)

        self._save_photo(frame, PHOTO_STATUS_TAKEN)

    def _save_photo(self, frame, status):
        pos = SHOOT_POSITIONS[self.current_position_index]
        visit_dir = self.visit.get_visit_dir(self.patient.name, self.patient.id)
        timestamp = datetime.now().strftime('%H%M%S_%f')
        filename = f'{pos["code"]}_{timestamp}.jpg'
        filepath = os.path.join(visit_dir, filename)

        cv2.imwrite(filepath, frame)

        photo = Photo(
            visit_id=self.visit_id,
            position_code=pos['code'],
            file_path=filepath,
            file_name=filename,
            status=status,
            taken_at=datetime.now(),
            imported=False
        )
        photo_id = Database.add_photo(photo)
        photo.id = photo_id

        self.position_photos[pos['code']] = photo
        self.position_statuses[pos['code']] = status
        self.position_widgets[pos['code']].set_status(status)

        self._update_progress()
        self._update_retake_button()

        if status == PHOTO_STATUS_TAKEN and self.current_position_index < len(SHOOT_POSITIONS) - 1:
            QTimer.singleShot(300, self._next_position)
        elif self._check_all_completed():
            self._show_completion_message()

    def _skip_position(self):
        pos = SHOOT_POSITIONS[self.current_position_index]
        old_status = self.position_statuses.get(pos['code'], PHOTO_STATUS_PENDING)

        if old_status == PHOTO_STATUS_TAKEN and pos['code'] in self.position_photos:
            reply = QMessageBox.question(
                self, '确认跳过',
                f'「{pos["name"]}」已有照片，确定要标记为跳过吗？\n（已有照片会被保留）',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

        self._update_position_status(pos['code'], PHOTO_STATUS_SKIPPED)

        if self.current_position_index < len(SHOOT_POSITIONS) - 1:
            QTimer.singleShot(200, self._next_position)
        elif self._check_all_completed():
            self._show_completion_message()

    def _mark_missing(self):
        pos = SHOOT_POSITIONS[self.current_position_index]
        old_status = self.position_statuses.get(pos['code'], PHOTO_STATUS_PENDING)

        if old_status == PHOTO_STATUS_TAKEN and pos['code'] in self.position_photos:
            reply = QMessageBox.question(
                self, '确认缺拍',
                f'「{pos["name"]}」已有照片，确定要标记为缺拍吗？\n（已有照片会被删除）',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return

            if pos['code'] in self.position_photos and self.position_photos[pos['code']].id:
                Database.delete_photo(self.position_photos[pos['code']].id, delete_file=True)
                del self.position_photos[pos['code']]

        self._update_position_status(pos['code'], PHOTO_STATUS_MISSING)

        if self.current_position_index < len(SHOOT_POSITIONS) - 1:
            QTimer.singleShot(200, self._next_position)
        elif self._check_all_completed():
            self._show_completion_message()

    def _update_position_status(self, position_code, status):
        self.position_statuses[position_code] = status
        self.position_widgets[position_code].set_status(status)

        if position_code in self.position_photos:
            photo = self.position_photos[position_code]
            photo.status = status
            if photo.id:
                Database.update_photo_status(photo.id, status)
        else:
            photo = Photo(
                visit_id=self.visit_id,
                position_code=position_code,
                status=status,
                imported=False
            )
            photo_id = Database.add_photo(photo)
            photo.id = photo_id
            self.position_photos[position_code] = photo

        self._update_progress()
        self._update_retake_button()
        self.position_label.setText(self._get_current_position_text())

    def _check_all_completed(self):
        for pos in SHOOT_POSITIONS:
            status = self.position_statuses.get(pos['code'], PHOTO_STATUS_PENDING)
            if status == PHOTO_STATUS_PENDING:
                return False
        return True

    def _show_completion_message(self):
        taken = sum(1 for s in self.position_statuses.values() if s == PHOTO_STATUS_TAKEN)
        missing = sum(1 for s in self.position_statuses.values() if s == PHOTO_STATUS_MISSING)
        skipped = sum(1 for s in self.position_statuses.values() if s == PHOTO_STATUS_SKIPPED)

        msg = f'采集完成！\n\n✓ 已拍：{taken} 张\n⚠ 缺拍：{missing} 张\n⏭ 跳过：{skipped} 张'
        reply = QMessageBox.information(self, '完成', msg)

    def _next_position(self):
        if self.current_position_index < len(SHOOT_POSITIONS) - 1:
            self._jump_to_position(self.current_position_index + 1)

    def _prev_position(self):
        if self.current_position_index > 0:
            self._jump_to_position(self.current_position_index - 1)

    def _update_position(self):
        self.position_label.setText(self._get_current_position_text())
        self.prev_btn.setEnabled(self.current_position_index > 0)
        self.next_btn.setEnabled(self.current_position_index < len(SHOOT_POSITIONS) - 1)

    def _update_progress(self):
        taken = sum(1 for s in self.position_statuses.values() if s == PHOTO_STATUS_TAKEN)
        missing = sum(1 for s in self.position_statuses.values() if s == PHOTO_STATUS_MISSING)
        skipped = sum(1 for s in self.position_statuses.values() if s == PHOTO_STATUS_SKIPPED)
        completed = taken + missing + skipped

        self.progress_bar.setValue(completed)
        self.progress_bar.setFormat(f'已完成 {completed}/{len(SHOOT_POSITIONS)}')
        self.count_label.setText(f'已拍{taken} 缺{missing} 跳{skipped}')

    def _update_retake_button(self):
        pos = SHOOT_POSITIONS[self.current_position_index]
        can_retake = self.position_statuses.get(pos['code']) == PHOTO_STATUS_TAKEN
        self.retake_btn.setEnabled(can_retake)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self._capture_photo()
        elif event.key() == Qt.Key_R:
            self._retake_photo()
        elif event.key() == Qt.Key_S:
            self._skip_position()
        elif event.key() == Qt.Key_M:
            self._mark_missing()
        elif event.key() == Qt.Key_Right:
            self._next_position()
        elif event.key() == Qt.Key_Left:
            self._prev_position()
        elif event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.timer.stop()
        if self.camera is not None:
            self.camera.release()
            self.camera = None
        self.capture_finished.emit()
        super().closeEvent(event)
