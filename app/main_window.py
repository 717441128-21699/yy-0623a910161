import os
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QMessageBox, QDialog,
    QComboBox, QSpinBox, QDialogButtonBox, QTimeEdit, QFileDialog
)
from PySide6.QtCore import Qt, Signal, QTime
from PySide6.QtGui import QFont, QColor
from datetime import date, time

from .database import Database
from .models import Patient, Visit, TREATMENT_STAGES


class AddPatientDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('新增患者')
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form_layout = QVBoxLayout()
        form_layout.setSpacing(8)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('患者姓名 *')
        form_layout.addWidget(self.name_edit)

        row1 = QHBoxLayout()
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText('联系电话')
        row1.addWidget(self.phone_edit, 1)
        self.mrn_edit = QLineEdit()
        self.mrn_edit.setPlaceholderText('病历号')
        row1.addWidget(self.mrn_edit, 1)
        form_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.age_spin = QSpinBox()
        self.age_spin.setRange(0, 100)
        self.age_spin.setPrefix('年龄: ')
        row2.addWidget(self.age_spin, 1)
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(['', '男', '女'])
        self.gender_combo.setPlaceholderText('性别')
        row2.addWidget(self.gender_combo, 1)
        form_layout.addLayout(row2)

        self.plan_edit = QLineEdit()
        self.plan_edit.setPlaceholderText('治疗方案（如：正畸、种植）')
        form_layout.addWidget(self.plan_edit)

        row3 = QHBoxLayout()
        stage_label = QLabel('疗程阶段:')
        self.stage_combo = QComboBox()
        for stage in TREATMENT_STAGES:
            self.stage_combo.addItem(stage['name'], stage['code'])
        row3.addWidget(stage_label)
        row3.addWidget(self.stage_combo, 1)
        time_label = QLabel('预约时间:')
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat('HH:mm')
        self.time_edit.setTime(QTime(9, 0))
        self.time_edit.setMinimumTime(QTime(8, 0))
        self.time_edit.setMaximumTime(QTime(20, 0))
        row3.addWidget(time_label)
        row3.addWidget(self.time_edit, 1)
        form_layout.addLayout(row3)

        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_patient_data(self):
        time_val = self.time_edit.time()
        appointment_time = time(time_val.hour(), time_val.minute())
        patient = Patient(
            name=self.name_edit.text().strip(),
            phone=self.phone_edit.text().strip(),
            medical_record_number=self.mrn_edit.text().strip(),
            age=self.age_spin.value() if self.age_spin.value() > 0 else None,
            gender=self.gender_combo.currentText(),
            treatment_plan=self.plan_edit.text().strip()
        )
        return patient, self.stage_combo.currentData(), appointment_time


class MainWindow(QMainWindow):
    start_capture = Signal(int, int)
    start_organize = Signal(int, int)
    start_compare = Signal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle('口腔拍照归档工具')
        self.resize(1050, 720)
        self.patient_visits = {}
        self._init_ui()
        self._load_visit_list()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        header_row = QHBoxLayout()
        header = QLabel(f"今日复诊名单")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header.setFont(header_font)
        header_row.addWidget(header)
        header_row.addStretch()

        import_btn = QPushButton('📥 导入')
        import_btn.setStyleSheet('''
            QPushButton {
                background: #2e7d32;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background: #1b5e20; }
        ''')
        import_btn.clicked.connect(self._on_import_csv)
        header_row.addWidget(import_btn)

        left_layout.addLayout(header_row)

        date_label = QLabel(date.today().strftime('%Y年%m月%d日  %A'))
        date_label.setStyleSheet('color: #666; font-size: 13px;')
        left_layout.addWidget(date_label)

        self.visit_list = QListWidget()
        self.visit_list.itemDoubleClicked.connect(self._on_visit_double_clicked)
        self.visit_list.itemSelectionChanged.connect(self.on_visit_selection_changed)
        self.visit_list.setStyleSheet('''
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 8px;
                background: white;
                font-size: 13px;
            }
            QListWidget::item {
                padding: 10px 12px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background: #e3f2fd;
                color: #1565c0;
            }
        ''')
        left_layout.addWidget(self.visit_list, 1)

        btn_row = QHBoxLayout()
        add_btn = QPushButton('+ 新增')
        add_btn.setStyleSheet('''
            QPushButton {
                background: #1976d2;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover { background: #1565c0; }
        ''')
        add_btn.clicked.connect(self._on_add_patient)
        btn_row.addWidget(add_btn, 1)

        refresh_btn = QPushButton('⟳ 刷新')
        refresh_btn.setStyleSheet('''
            QPushButton {
                background: #78909c;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 6px;
                font-size: 13px;
            }
            QPushButton:hover { background: #546e7a; }
        ''')
        refresh_btn.clicked.connect(self._load_visit_list)
        btn_row.addWidget(refresh_btn, 1)
        left_layout.addLayout(btn_row)

        main_layout.addWidget(left_panel, 1)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)

        title = QLabel('选择操作')
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        right_layout.addWidget(title)

        right_layout.addStretch()

        self.capture_btn = QPushButton('📷  拍照采集')
        self._style_large_button(self.capture_btn, '#4caf50')
        self.capture_btn.clicked.connect(self._on_capture_clicked)
        right_layout.addWidget(self.capture_btn)

        self.organize_btn = QPushButton('📂  照片归位')
        self._style_large_button(self.organize_btn, '#ff9800')
        self.organize_btn.clicked.connect(self._on_organize_clicked)
        right_layout.addWidget(self.organize_btn)

        self.compare_btn = QPushButton('📊  复诊对比')
        self._style_large_button(self.compare_btn, '#9c27b0')
        self.compare_btn.clicked.connect(self._on_compare_clicked)
        right_layout.addWidget(self.compare_btn)

        right_layout.addStretch()

        self.status_label = QLabel('请先在左侧选择患者')
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet('color: #999;')
        right_layout.addWidget(self.status_label)

        right_layout.addStretch()

        main_layout.addWidget(right_panel, 2)

        self._set_buttons_enabled(False)

    def _style_large_button(self, btn, color):
        btn.setMinimumHeight(80)
        btn.setStyleSheet(f'''
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 20px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: {self._darken_color(color)};
            }}
            QPushButton:disabled {{
                background: #ccc;
                color: #999;
            }}
        ''')

    def _darken_color(self, hex_color):
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        factor = 0.85
        return f'#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}'

    def _set_buttons_enabled(self, enabled):
        self.capture_btn.setEnabled(enabled)
        self.organize_btn.setEnabled(enabled)
        self.compare_btn.setEnabled(enabled)

    def _load_visit_list(self):
        self.visit_list.clear()
        self.patient_visits.clear()

        visits = Database.get_today_visits()

        if not visits:
            item = QListWidgetItem('📋  暂无今日复诊患者\n点击「导入」从CSV导入预约名单，或点击「新增」添加')
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setTextAlignment(Qt.AlignCenter)
            self.visit_list.addItem(item)
            return

        for patient, visit in visits:
            stage_name = next(
                (s['name'] for s in TREATMENT_STAGES if s['code'] == visit.stage_code),
                visit.stage_code
            )

            time_display = visit.get_appointment_display()
            if time_display:
                time_text = f'🕐 {time_display}  '
            else:
                time_text = '⏱ 未安排  '

            item_text = f'{time_text}{patient.name}'

            identifier = patient.get_display_identifier()
            if identifier:
                item_text += f'\n   {identifier}'

            item_text += f'  |  {stage_name}'
            if patient.age:
                item_text += f'  |  {patient.age}岁'

            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, (patient.id, visit.id))

            if not time_display:
                item.setForeground(QColor('#999'))

            self.visit_list.addItem(item)

    def _on_import_csv(self):
        file_dialog = QFileDialog()
        file_path, _ = file_dialog.getOpenFileName(
            self,
            '选择预约名单CSV文件',
            '',
            'CSV文件 (*.csv)'
        )

        if not file_path:
            return

        reply = QMessageBox.question(
            self, '确认导入',
            f'确定要导入 {os.path.basename(file_path)} 吗？\n\n'
            'CSV格式要求：\n'
            '• 第一行为表头，必须包含「姓名」列\n'
            '• 可选列：电话、病历号、时间段、年龄、性别、治疗方案\n'
            '• 时间段格式：09:00、09.00、9点30分等',
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )

        if reply != QMessageBox.Yes:
            return

        imported_count, errors = Database.import_appointments_from_csv(file_path)

        self._load_visit_list()

        if imported_count > 0:
            msg = f'✓ 成功导入 {imported_count} 条预约'
            if errors:
                msg += f'\n\n⚠ 存在 {len(errors)} 个问题：\n' + '\n'.join(errors[:10])
                if len(errors) > 10:
                    msg += f'\n... 还有 {len(errors) - 10} 条问题未显示'
            QMessageBox.information(self, '导入完成', msg)
        else:
            if errors:
                QMessageBox.warning(self, '导入失败', '\n'.join(errors))
            else:
                QMessageBox.information(self, '导入完成', '没有新的预约需要导入')

    def _on_visit_double_clicked(self, item):
        data = item.data(Qt.UserRole)
        if data:
            patient_id, visit_id = data
            self.start_capture.emit(patient_id, visit_id)

    def _on_capture_clicked(self):
        data = self._get_selected_data()
        if data:
            self.start_capture.emit(*data)

    def _on_organize_clicked(self):
        data = self._get_selected_data()
        if data:
            self.start_organize.emit(*data)

    def _on_compare_clicked(self):
        data = self._get_selected_data()
        if data:
            self.start_compare.emit(data[0])

    def _get_selected_data(self):
        item = self.visit_list.currentItem()
        if item:
            data = item.data(Qt.UserRole)
            if data:
                return data
        QMessageBox.warning(self, '提示', '请先选择一个患者')
        return None

    def _on_add_patient(self):
        dialog = AddPatientDialog(self)
        if dialog.exec() == QDialog.Accepted:
            patient, stage_code, appointment_time = dialog.get_patient_data()

            if not patient.name:
                QMessageBox.warning(self, '提示', '请输入患者姓名')
                return

            patient_id = Database.add_patient(patient)
            visit = Visit(
                patient_id=patient_id,
                visit_date=date.today(),
                appointment_time=appointment_time,
                stage_code=stage_code
            )
            visit_id = Database.add_visit(visit)

            self._load_visit_list()
            QMessageBox.information(self, '成功', f'已添加患者：{patient.name}')

    def showEvent(self, event):
        self._load_visit_list()
        super().showEvent(event)

    def on_visit_selection_changed(self):
        has_selection = self.visit_list.currentItem() and \
            self.visit_list.currentItem().data(Qt.UserRole) is not None
        self._set_buttons_enabled(has_selection)
        if has_selection:
            self.status_label.setText('已选择患者，选择上方操作')
        else:
            self.status_label.setText('请先在左侧选择患者')

    def on_subwindow_closed(self):
        self._load_visit_list()
