import os
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QMessageBox, QDialog, QComboBox, QFrame, QScrollArea,
    QInputDialog, QCheckBox, QSlider, QSplitter
)
from PySide6.QtCore import Qt, Signal, QPoint, QRect, QSize
from PySide6.QtGui import (
    QPixmap, QFont, QPainter, QColor, QPen, QBrush,
    QMouseEvent, QPaintEvent, QImage
)

from .database import Database
from .models import Patient, Visit, Photo, Note, SHOOT_POSITIONS, TREATMENT_STAGES


class PhotoCompareWidget(QFrame):
    note_added = Signal(int, str, float, float)
    note_clicked = Signal(int)

    def __init__(self, photo: Photo = None, show_ruler: bool = False, parent=None):
        super().__init__(parent)
        self.photo = photo
        self.show_ruler = show_ruler
        self.zoom = 1.0
        self.pan_offset = QPoint(0, 0)
        self.panning = False
        self.last_pan_point = QPoint()
        self.notes = []
        self.setMinimumSize(400, 350)
        self.setMouseTracking(True)
        self.setAcceptDrops(False)
        self.setStyleSheet('''
            PhotoCompareWidget {
                background: #212121;
                border: 1px solid #424242;
                border-radius: 8px;
            }
        ''')

    def set_photo(self, photo: Photo):
        self.photo = photo
        if photo:
            self.notes = Database.get_photo_notes(photo.id)
        else:
            self.notes = []
        self.zoom = 1.0
        self.pan_offset = QPoint(0, 0)
        self.update()

    def set_show_ruler(self, show: bool):
        self.show_ruler = show
        self.update()

    def add_note(self, content: str, x: float, y: float):
        if self.photo:
            note = Note(
                photo_id=self.photo.id,
                content=content,
                x=x,
                y=y
            )
            note_id = Database.add_note(note)
            note.id = note_id
            self.notes.append(note)
            self.update()

    def clear_notes(self):
        self.notes = []
        self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        rect = self.rect()
        painter.fillRect(rect, QColor(33, 33, 33))

        if not self.photo or not os.path.exists(self.photo.file_path):
            painter.setPen(QColor(158, 158, 158))
            painter.setFont(QFont('Arial', 14))
            painter.drawText(rect, Qt.AlignCenter, '暂无照片')
            return

        pixmap = QPixmap(self.photo.file_path)
        if pixmap.isNull():
            painter.setPen(QColor(158, 158, 158))
            painter.drawText(rect, Qt.AlignCenter, '照片加载失败')
            return

        scaled_width = int(pixmap.width() * self.zoom)
        scaled_height = int(pixmap.height() * self.zoom)
        scaled_pixmap = pixmap.scaled(
            scaled_width, scaled_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        x = (rect.width() - scaled_width) // 2 + self.pan_offset.x()
        y = (rect.height() - scaled_height) // 2 + self.pan_offset.y()

        self._image_rect = QRect(x, y, scaled_width, scaled_height)
        painter.drawPixmap(x, y, scaled_pixmap)

        if self.show_ruler:
            self._draw_ruler(painter, rect)

        for note in self.notes:
            note_x = x + int(note.x * scaled_width)
            note_y = y + int(note.y * scaled_height)

            painter.setBrush(QBrush(QColor(244, 67, 54, 200)))
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawEllipse(note_x - 8, note_y - 8, 16, 16)

            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.setFont(QFont('Arial', 9, QFont.Bold))
            painter.drawText(note_x - 4, note_y + 4, '!')

            label_rect = QRect(note_x + 15, note_y - 20, 180, 40)
            painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(label_rect, 4, 4)

            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.setFont(QFont('Arial', 9))
            painter.drawText(label_rect.adjusted(8, 5, -5, -5), Qt.TextWordWrap, note.content)

    def _draw_ruler(self, painter: QPainter, rect: QRect):
        pen = QPen(QColor(255, 255, 255, 180))
        pen.setWidth(1)
        pen.setStyle(Qt.DashLine)
        painter.setPen(pen)

        center_x = rect.width() // 2
        center_y = rect.height() // 2

        painter.drawLine(center_x, 0, center_x, rect.height())
        painter.drawLine(0, center_y, rect.width(), center_y)

        painter.drawLine(0, rect.height() // 3, rect.width(), rect.height() // 3)
        painter.drawLine(0, rect.height() * 2 // 3, rect.width(), rect.height() * 2 // 3)

        painter.drawLine(rect.width() // 3, 0, rect.width() // 3, rect.height())
        painter.drawLine(rect.width() * 2 // 3, 0, rect.width() * 2 // 3, rect.height())

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            if self.photo and hasattr(self, '_image_rect') and self._image_rect.contains(event.position().toPoint()):
                rel_x = (event.position().x() - self._image_rect.x()) / self._image_rect.width()
                rel_y = (event.position().y() - self._image_rect.y()) / self._image_rect.height()

                for note in self.notes:
                    note_x = self._image_rect.x() + int(note.x * self._image_rect.width())
                    note_y = self._image_rect.y() + int(note.y * self._image_rect.height())
                    if abs(event.position().x() - note_x) < 12 and abs(event.position().y() - note_y) < 12:
                        reply = QMessageBox.question(
                            self, '删除备注',
                            f'是否删除备注：「{note.content}」？',
                            QMessageBox.Yes | QMessageBox.No,
                            QMessageBox.No
                        )
                        if reply == QMessageBox.Yes:
                            Database.delete_note(note.id)
                            self.notes.remove(note)
                            self.update()
                        return

                content, ok = QInputDialog.getText(
                    self, '添加备注',
                    '请输入观察点描述（如：牙缝关闭、扭转牙改善）：'
                )
                if ok and content.strip():
                    self.add_note(content.strip(), rel_x, rel_y)
                    self.note_added.emit(self.photo.id, content.strip(), rel_x, rel_y)
            else:
                self.panning = True
                self.last_pan_point = event.position().toPoint()

        elif event.button() == Qt.RightButton:
            self.zoom = 1.0
            self.pan_offset = QPoint(0, 0)
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.panning:
            delta = event.position().toPoint() - self.last_pan_point
            self.pan_offset += delta
            self.last_pan_point = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.panning = False

    def wheelEvent(self, event):
        if self.photo:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom = min(self.zoom * 1.1, 3.0)
            else:
                self.zoom = max(self.zoom / 1.1, 0.3)
            self.update()

    def render_to_image(self, width: int = 800, height: int = 600) -> QImage:
        image = QImage(width, height, QImage.Format_RGB32)
        image.fill(QColor(33, 33, 33))

        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        rect = QRect(0, 0, width, height)

        if not self.photo or not os.path.exists(self.photo.file_path):
            painter.setPen(QColor(158, 158, 158))
            painter.setFont(QFont('Arial', 16))
            painter.drawText(rect, Qt.AlignCenter, '暂无照片')
            painter.end()
            return image

        pixmap = QPixmap(self.photo.file_path)
        if pixmap.isNull():
            painter.setPen(QColor(158, 158, 158))
            painter.drawText(rect, Qt.AlignCenter, '照片加载失败')
            painter.end()
            return image

        scaled_pixmap = pixmap.scaled(
            width, height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        x = (width - scaled_pixmap.width()) // 2
        y = (height - scaled_pixmap.height()) // 2
        img_rect = QRect(x, y, scaled_pixmap.width(), scaled_pixmap.height())

        painter.drawPixmap(x, y, scaled_pixmap)

        if self.show_ruler:
            pen = QPen(QColor(255, 255, 255, 180))
            pen.setWidth(1)
            pen.setStyle(Qt.DashLine)
            painter.setPen(pen)

            center_x = width // 2
            center_y = height // 2

            painter.drawLine(center_x, 0, center_x, height)
            painter.drawLine(0, center_y, width, center_y)
            painter.drawLine(0, height // 3, width, height // 3)
            painter.drawLine(0, height * 2 // 3, width, height * 2 // 3)
            painter.drawLine(width // 3, 0, width // 3, height)
            painter.drawLine(width * 2 // 3, 0, width * 2 // 3, height)

        for note in self.notes:
            note_x = x + int(note.x * scaled_pixmap.width())
            note_y = y + int(note.y * scaled_pixmap.height())

            painter.setBrush(QBrush(QColor(244, 67, 54, 200)))
            painter.setPen(QPen(QColor(255, 255, 255), 2))
            painter.drawEllipse(note_x - 10, note_y - 10, 20, 20)

            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.setFont(QFont('Arial', 11, QFont.Bold))
            painter.drawText(note_x - 5, note_y + 5, '!')

            label_rect = QRect(note_x + 20, note_y - 25, 200, 50)
            painter.setBrush(QBrush(QColor(0, 0, 0, 180)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(label_rect, 6, 6)

            painter.setPen(QPen(QColor(255, 255, 255)))
            painter.setFont(QFont('Arial', 10))
            painter.drawText(label_rect.adjusted(10, 6, -8, -8), Qt.TextWordWrap, note.content)

        painter.end()
        return image


class CompareWindow(QDialog):
    compare_finished = Signal()

    def __init__(self, patient_id: int, parent=None):
        super().__init__(parent)
        self.patient_id = patient_id
        self.patient = Database.get_patient(patient_id)
        self.visits = Database.get_patient_visits(patient_id)
        self.visit_photos = {}

        self.setWindowTitle(f'复诊对比 - {self.patient.name}')
        self.resize(1200, 800)
        self.setModal(True)

        self._init_ui()
        self._load_visits()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)

        header_layout = QHBoxLayout()

        title = QLabel(f'患者：{self.patient.name}')
        title.setStyleSheet('font-size: 16px; font-weight: bold; color: #333;')
        header_layout.addWidget(title)
        header_layout.addStretch()

        header_layout.addWidget(QLabel('早期：'))
        self.visit1_combo = QComboBox()
        self.visit1_combo.setMinimumWidth(200)
        self.visit1_combo.currentIndexChanged.connect(self._on_visit_changed)
        header_layout.addWidget(self.visit1_combo)

        header_layout.addSpacing(20)
        header_layout.addWidget(QLabel('→'))
        header_layout.addSpacing(20)

        header_layout.addWidget(QLabel('后期：'))
        self.visit2_combo = QComboBox()
        self.visit2_combo.setMinimumWidth(200)
        self.visit2_combo.currentIndexChanged.connect(self._on_visit_changed)
        header_layout.addWidget(self.visit2_combo)

        header_layout.addStretch()

        self.ruler_checkbox = QCheckBox('显示标尺线')
        self.ruler_checkbox.setStyleSheet('padding: 8px;')
        self.ruler_checkbox.toggled.connect(self._toggle_ruler)
        header_layout.addWidget(self.ruler_checkbox)

        header_layout.addSpacing(10)

        self.export_btn = QPushButton('📄  导出对比报告')
        self.export_btn.setStyleSheet('''
            QPushButton {
                background: #4caf50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover { background: #388e3c; }
            QPushButton:disabled {
                background: #ccc;
            }
        ''')
        self.export_btn.clicked.connect(self._export_report)
        header_layout.addWidget(self.export_btn)

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

        self.position_bar = QHBoxLayout()
        self.position_buttons = {}
        for pos in SHOOT_POSITIONS:
            btn = QPushButton(pos['name'])
            btn.setCheckable(True)
            btn.setMinimumHeight(40)
            btn.setStyleSheet('''
                QPushButton {
                    background: #f5f5f5;
                    border: 1px solid #ddd;
                    border-radius: 6px;
                    padding: 8px 16px;
                    font-size: 13px;
                }
                QPushButton:checked {
                    background: #1976d2;
                    color: white;
                    border-color: #1565c0;
                }
                QPushButton:hover:not(:checked) {
                    background: #eeeeee;
                }
            ''')
            btn.clicked.connect(lambda checked, code=pos['code']: self._select_position(code))
            self.position_buttons[pos['code']] = btn
            self.position_bar.addWidget(btn)
        layout.addLayout(self.position_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet('''
            QScrollArea {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background: #fafafa;
            }
        ''')

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(20, 20, 20, 20)
        content_layout.setSpacing(15)

        self.position_label = QLabel()
        self.position_label.setAlignment(Qt.AlignCenter)
        self.position_label.setFont(QFont('Arial', 14, QFont.Bold))
        self.position_label.setStyleSheet('color: #1565c0;')
        content_layout.addWidget(self.position_label)

        compare_layout = QVBoxLayout()
        compare_layout.setSpacing(10)

        self.top_label = QLabel()
        self.top_label.setAlignment(Qt.AlignCenter)
        self.top_label.setStyleSheet('color: #757575; font-size: 12px;')
        compare_layout.addWidget(self.top_label)

        self.top_widget = PhotoCompareWidget()
        compare_layout.addWidget(self.top_widget, 1)

        self.bottom_label = QLabel()
        self.bottom_label.setAlignment(Qt.AlignCenter)
        self.bottom_label.setStyleSheet('color: #757575; font-size: 12px;')
        compare_layout.addWidget(self.bottom_label)

        self.bottom_widget = PhotoCompareWidget()
        compare_layout.addWidget(self.bottom_widget, 1)

        content_layout.addLayout(compare_layout, 1)

        tips = QLabel('💡 操作提示：点击照片添加观察点备注，滚轮缩放，左键拖动平移，右键重置。点击上方按钮切换不同拍摄角度进行对比。')
        tips.setStyleSheet('color: #757575; padding: 10px; background: #fff8e1; border-radius: 6px;')
        tips.setWordWrap(True)
        content_layout.addWidget(tips)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        self.status_label = QLabel('请选择两次复诊记录进行对比')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet('color: #666; padding-top: 8px;')
        layout.addWidget(self.status_label)

    def _load_visits(self):
        self.visit1_combo.clear()
        self.visit2_combo.clear()

        if not self.visits:
            QMessageBox.information(self, '提示', '该患者暂无复诊记录')
            return

        for visit in self.visits:
            stage_name = next(
                (s['name'] for s in TREATMENT_STAGES if s['code'] == visit.stage_code),
                visit.stage_code
            )
            label = f'{visit.visit_date} - {stage_name}'
            photos = Database.get_visit_photos(visit.id)
            self.visit_photos[visit.id] = {p.position_code: p for p in photos}

            if len(photos) > 0:
                label += f' ({len(photos)}张照片)'

            self.visit1_combo.addItem(label, visit.id)
            self.visit2_combo.addItem(label, visit.id)

        if len(self.visits) >= 2:
            self.visit2_combo.setCurrentIndex(0)
            self.visit1_combo.setCurrentIndex(min(1, len(self.visits) - 1))

        if self.position_buttons:
            first_pos = list(self.position_buttons.keys())[0]
            self.position_buttons[first_pos].setChecked(True)
            self._select_position(first_pos)

    def _on_visit_changed(self):
        current_position = None
        for code, btn in self.position_buttons.items():
            if btn.isChecked():
                current_position = code
                break
        if current_position:
            self._select_position(current_position)

    def _select_position(self, position_code: str):
        for code, btn in self.position_buttons.items():
            btn.setChecked(code == position_code)

        pos_name = next((p['name'] for p in SHOOT_POSITIONS if p['code'] == position_code), position_code)
        self.position_label.setText(f'拍摄角度：{pos_name}')

        visit1_id = self.visit1_combo.currentData() if self.visit1_combo.count() > 0 else None
        visit2_id = self.visit2_combo.currentData() if self.visit2_combo.count() > 0 else None

        photo1 = self.visit_photos.get(visit1_id, {}).get(position_code) if visit1_id else None
        photo2 = self.visit_photos.get(visit2_id, {}).get(position_code) if visit2_id else None

        visit1 = next((v for v in self.visits if v.id == visit1_id), None)
        visit2 = next((v for v in self.visits if v.id == visit2_id), None)

        stage1 = next((s['name'] for s in TREATMENT_STAGES if s['code'] == visit1.stage_code), '') if visit1 else ''
        stage2 = next((s['name'] for s in TREATMENT_STAGES if s['code'] == visit2.stage_code), '') if visit2 else ''

        self.top_widget.set_photo(photo1)
        self.bottom_widget.set_photo(photo2)

        date1 = visit1.visit_date if visit1 else '未选择'
        date2 = visit2.visit_date if visit2 else '未选择'

        self.top_label.setText(f'▲ 早期：{date1}  {stage1}')
        self.bottom_label.setText(f'▼ 后期：{date2}  {stage2}')

        status_parts = []
        if photo1:
            status_parts.append('早期照片：✓')
        else:
            status_parts.append('早期照片：✗')
        if photo2:
            status_parts.append('后期照片：✓')
        else:
            status_parts.append('后期照片：✗')

        self.status_label.setText('  |  '.join(status_parts))

    def _toggle_ruler(self, checked: bool):
        self.top_widget.set_show_ruler(checked)
        self.bottom_widget.set_show_ruler(checked)

    def _export_report(self):
        visit1_id = self.visit1_combo.currentData() if self.visit1_combo.count() > 0 else None
        visit2_id = self.visit2_combo.currentData() if self.visit2_combo.count() > 0 else None

        if not visit1_id or not visit2_id:
            QMessageBox.warning(self, '提示', '请先选择两次复诊记录')
            return

        current_position = None
        for code, btn in self.position_buttons.items():
            if btn.isChecked():
                current_position = code
                break

        if not current_position:
            QMessageBox.warning(self, '提示', '请先选择一个拍摄角度')
            return

        photo1 = self.visit_photos.get(visit1_id, {}).get(current_position)
        photo2 = self.visit_photos.get(visit2_id, {}).get(current_position)

        if not photo1 and not photo2:
            QMessageBox.warning(self, '提示', '当前角度没有照片可以导出')
            return

        pos_name = next((p['name'] for p in SHOOT_POSITIONS if p['code'] == current_position), current_position)
        visit1 = next((v for v in self.visits if v.id == visit1_id), None)
        visit2 = next((v for v in self.visits if v.id == visit2_id), None)

        stage1 = next((s['name'] for s in TREATMENT_STAGES if s['code'] == visit1.stage_code), '') if visit1 else ''
        stage2 = next((s['name'] for s in TREATMENT_STAGES if s['code'] == visit2.stage_code), '') if visit2 else ''

        date1 = visit1.visit_date if visit1 else '未选择'
        date2 = visit2.visit_date if visit2 else '未选择'

        img_width = 1000
        header_height = 120
        img_height = header_height + 600 * 2 + 40

        report_image = QImage(img_width, img_height, QImage.Format_RGB32)
        report_image.fill(QColor(255, 255, 255))

        painter = QPainter(report_image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        header_rect = QRect(0, 0, img_width, header_height)
        painter.fillRect(header_rect, QColor(15, 101, 192))

        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont('Microsoft YaHei', 20, QFont.Bold))
        painter.drawText(header_rect, Qt.AlignHCenter | Qt.AlignTop, '口腔正畸复诊对比报告')

        painter.setFont(QFont('Microsoft YaHei', 12))
        info_text = f'患者：{self.patient.name}'
        if self.patient.medical_record_number:
            info_text += f'  |  病历号：{self.patient.medical_record_number}'
        if self.patient.phone:
            info_text += f'  |  电话：{self.patient.phone}'
        painter.drawText(header_rect.adjusted(30, 50, -30, 0), Qt.AlignLeft | Qt.AlignTop, info_text)

        pos_text = f'拍摄角度：{pos_name}'
        painter.drawText(header_rect.adjusted(30, 75, -30, 0), Qt.AlignLeft | Qt.AlignTop, pos_text)

        export_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        painter.drawText(header_rect.adjusted(-30, 75, -30, 0), Qt.AlignRight | Qt.AlignTop, f'导出时间：{export_time}')

        top_img = self.top_widget.render_to_image(940, 580)
        bottom_img = self.bottom_widget.render_to_image(940, 580)

        top_y = header_height + 20
        painter.drawImage(30, top_y, top_img)

        top_label_rect = QRect(30, top_y + 10, 940, 30)
        painter.fillRect(top_label_rect, QColor(0, 0, 0, 150))
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont('Microsoft YaHei', 11, QFont.Bold))
        painter.drawText(top_label_rect.adjusted(15, 0, -15, 0), Qt.AlignVCenter | Qt.AlignLeft,
                         f'▲ 早期：{date1}  {stage1}')

        bottom_y = header_height + 20 + 600
        painter.drawImage(30, bottom_y, bottom_img)

        bottom_label_rect = QRect(30, bottom_y + 10, 940, 30)
        painter.fillRect(bottom_label_rect, QColor(0, 0, 0, 150))
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(bottom_label_rect.adjusted(15, 0, -15, 0), Qt.AlignVCenter | Qt.AlignLeft,
                         f'▼ 后期：{date2}  {stage2}')

        painter.end()

        patient_dir = self.patient.get_photo_dir()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"对比报告_{pos_name}_{date1}_vs_{date2}_{timestamp}.png"
        save_path = os.path.join(patient_dir, filename)

        if report_image.save(save_path, 'PNG'):
            QMessageBox.information(self, '导出成功', f'对比报告已保存到：\n{save_path}')
        else:
            QMessageBox.critical(self, '导出失败', '保存图片时发生错误，请检查文件夹权限')

    def closeEvent(self, event):
        self.compare_finished.emit()
        super().closeEvent(event)
