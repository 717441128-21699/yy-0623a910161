import cv2
import numpy as np
import os
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QMessageBox, QDialog
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QImage, QPixmap, QFont, QPainter, QColor, QPen

from .database import Database
from .models import Patient, Visit, Photo, SHOOT_POSITIONS, TREATMENT_STAGES


class CaptureWindow(QDialog):
    capture_finished = Signal()

    def __init__(self, patient_id: int, visit_id: int, parent=None):
        super().__init__(parent)
        self.patient_id = patient_id
        self.visit_id = visit_id
        self.patient = Database.get_patient(patient_id)
        self.visit = Database.get_visit(visit_id)

        self.current_position_index = 0
        self.captured_positions = set()
        self.camera = None
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_frame)

        self.setWindowTitle(f'拍照采集 - {self.patient.name}')
        self.resize(1000, 750)
        self.setModal(True)

        self._init_ui()
        self._start_camera()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        header_layout = QHBoxLayout()

        stage_name = next(
            (s['name'] for s in TREATMENT_STAGES if s['code'] == self.visit.stage_code),
            self.visit.stage_code
        )
        patient_info = QLabel(f'患者：{self.patient.name}  |  疗程：{stage_name}  |  {self.visit.visit_date}')
        patient_info.setStyleSheet('font-size: 14px; color: #333;')
        header_layout.addWidget(patient_info)
        header_layout.addStretch()

        position_label = QLabel(self._get_current_position_text())
        position_label.setAlignment(Qt.AlignCenter)
        position_font = QFont()
        position_font.setPointSize(22)
        position_font.setBold(True)
        position_label.setFont(position_font)
        position_label.setStyleSheet('color: #1565c0;')
        self.position_label = position_label
        header_layout.addWidget(position_label, 1)
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

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(len(SHOOT_POSITIONS))
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(f'已完成 0/{len(SHOOT_POSITIONS)}')
        self.progress_bar.setStyleSheet('''
            QProgressBar {
                border: 1px solid #bdbdbd;
                border-radius: 6px;
                text-align: center;
                height: 24px;
            }
            QProgressBar::chunk {
                background: #4caf50;
                border-radius: 6px;
            }
        ''')
        layout.addWidget(self.progress_bar)

        self.video_label = QLabel()
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet('background: #000; border-radius: 8px;')
        self.video_label.setMinimumHeight(450)
        layout.addWidget(self.video_label, 1)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        self.prev_btn = QPushButton('← 上一张')
        self._style_nav_button(self.prev_btn, '#78909c')
        self.prev_btn.clicked.connect(self._prev_position)
        self.prev_btn.setEnabled(False)
        btn_layout.addWidget(self.prev_btn)

        self.capture_btn = QPushButton('📸  拍照 (空格键)')
        self.capture_btn.setMinimumHeight(60)
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
        btn_layout.addWidget(self.capture_btn, 2)

        self.next_btn = QPushButton('下一张 →')
        self._style_nav_button(self.next_btn, '#78909c')
        self.next_btn.clicked.connect(self._next_position)
        btn_layout.addWidget(self.next_btn)

        layout.addLayout(btn_layout)

        tips = QLabel('提示：按空格键拍照，方向键切换拍摄位，拍完自动进入下一张')
        tips.setAlignment(Qt.AlignCenter)
        tips.setStyleSheet('color: #999; font-size: 12px;')
        layout.addWidget(tips)

    def _style_nav_button(self, btn, color):
        btn.setMinimumHeight(60)
        btn.setStyleSheet(f'''
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 16px;
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
        return f'第 {pos["order"]}/{len(SHOOT_POSITIONS)} 张：{pos["name"]}'

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
            font.setPointSize(16)
            font.setBold(True)
            painter.setFont(font)

            painter.drawText(20, 35, f'{pos["order"]}. {pos["name"]}')

            if self.current_position_index in self.captured_positions:
                painter.setPen(QPen(QColor(76, 175, 80)))
                painter.drawText(scaled_pixmap.width() - 80, 35, '✓ 已拍')

            painter.end()

            self.video_label.setPixmap(scaled_pixmap)

    def _capture_photo(self):
        if self.camera is None:
            return

        ret, frame = self.camera.read()
        if not ret:
            QMessageBox.warning(self, '错误', '拍照失败，请重试')
            return

        pos = SHOOT_POSITIONS[self.current_position_index]
        visit_dir = self.visit.get_visit_dir(self.patient.name, self.patient.id)
        timestamp = datetime.now().strftime('%H%M%S')
        filename = f'{pos["code"]}_{timestamp}.jpg'
        filepath = os.path.join(visit_dir, filename)

        cv2.imwrite(filepath, frame)

        photo = Photo(
            visit_id=self.visit_id,
            position_code=pos['code'],
            file_path=filepath,
            file_name=filename,
            taken_at=datetime.now(),
            imported=False
        )
        Database.add_photo(photo)

        self.captured_positions.add(self.current_position_index)
        self._update_progress()

        if self.current_position_index < len(SHOOT_POSITIONS) - 1:
            QTimer.singleShot(300, self._next_position)
        else:
            QMessageBox.information(self, '完成', '所有拍摄位已完成！')
            self.capture_finished.emit()

    def _next_position(self):
        if self.current_position_index < len(SHOOT_POSITIONS) - 1:
            self.current_position_index += 1
            self._update_position()

    def _prev_position(self):
        if self.current_position_index > 0:
            self.current_position_index -= 1
            self._update_position()

    def _update_position(self):
        self.position_label.setText(self._get_current_position_text())
        self.prev_btn.setEnabled(self.current_position_index > 0)
        self.next_btn.setEnabled(self.current_position_index < len(SHOOT_POSITIONS) - 1)

    def _update_progress(self):
        captured = len(self.captured_positions)
        self.progress_bar.setValue(captured)
        self.progress_bar.setFormat(f'已完成 {captured}/{len(SHOOT_POSITIONS)}')

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Space:
            self._capture_photo()
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
