import os
from datetime import date, time, timedelta
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QMessageBox, QDialog,
    QComboBox, QSpinBox, QDialogButtonBox, QTimeEdit, QFileDialog,
    QDateEdit, QFrame, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTime, QDate
from PySide6.QtGui import QFont, QColor

from .database import Database, ImportResult
from .models import Patient, Visit, TREATMENT_STAGES, SHOOT_POSITIONS, PHOTO_STATUS_TAKEN


class AddPatientDialog(QDialog):
    def __init__(self, default_date: date, parent=None):
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
        date_label = QLabel('就诊日期:')
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat('yyyy-MM-dd')
        self.date_edit.setDate(QDate(default_date.year, default_date.month, default_date.day))
        row3.addWidget(date_label)
        row3.addWidget(self.date_edit, 1)
        form_layout.addLayout(row3)

        row4 = QHBoxLayout()
        stage_label = QLabel('疗程阶段:')
        self.stage_combo = QComboBox()
        for stage in TREATMENT_STAGES:
            self.stage_combo.addItem(stage['name'], stage['code'])
        row4.addWidget(stage_label)
        row4.addWidget(self.stage_combo, 1)
        time_label = QLabel('预约时间:')
        self.time_edit = QTimeEdit()
        self.time_edit.setDisplayFormat('HH:mm')
        self.time_edit.setTime(QTime(9, 0))
        self.time_edit.setMinimumTime(QTime(8, 0))
        self.time_edit.setMaximumTime(QTime(20, 0))
        row4.addWidget(time_label)
        row4.addWidget(self.time_edit, 1)
        form_layout.addLayout(row4)

        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_patient_data(self):
        qd = self.date_edit.date()
        visit_date = date(qd.year(), qd.month(), qd.day())
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
        return patient, self.stage_combo.currentData(), appointment_time, visit_date


class ImportDialog(QDialog):
    def __init__(self, default_date: date, parent=None):
        super().__init__(parent)
        self.setWindowTitle('导入预约名单')
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        tip = QLabel(
            '选择要导入的预约名单文件和目标日期：\n'
            '• 支持格式：CSV、XLSX、XLS\n'
            '• 第一行为表头，必须包含「姓名」列\n'
            '• 可选列：电话、病历号、时间段、年龄、性别、治疗方案'
        )
        tip.setStyleSheet('color: #555; font-size: 12px; padding: 10px; background: #f5f5f5; border-radius: 6px;')
        tip.setWordWrap(True)
        layout.addWidget(tip)

        file_row = QHBoxLayout()
        file_label = QLabel('文件:')
        file_label.setFixedWidth(70)
        self.file_edit = QLineEdit()
        self.file_edit.setReadOnly(True)
        self.file_edit.setPlaceholderText('点击右侧按钮选择文件')
        browse_btn = QPushButton('浏览...')
        browse_btn.clicked.connect(self._on_browse)
        file_row.addWidget(file_label)
        file_row.addWidget(self.file_edit, 1)
        file_row.addWidget(browse_btn)
        layout.addLayout(file_row)

        date_row = QHBoxLayout()
        date_label = QLabel('导入到日期:')
        date_label.setFixedWidth(70)
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat('yyyy-MM-dd  dddd')
        self.date_edit.setDate(QDate(default_date.year, default_date.month, default_date.day))

        self.today_btn = QPushButton('今天')
        self.today_btn.clicked.connect(lambda: self._set_date(date.today()))
        self.tomorrow_btn = QPushButton('明天')
        self.tomorrow_btn.clicked.connect(lambda: self._set_date(date.today() + timedelta(days=1)))

        date_row.addWidget(date_label)
        date_row.addWidget(self.date_edit, 1)
        date_row.addWidget(self.today_btn)
        date_row.addWidget(self.tomorrow_btn)
        layout.addLayout(date_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText('开始导入')
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, '选择预约名单文件', '',
            '预约名单文件 (*.csv *.xlsx *.xls)'
        )
        if path:
            self.file_edit.setText(path)

    def _set_date(self, d: date):
        self.date_edit.setDate(QDate(d.year, d.month, d.day))

    def _on_accept(self):
        if not self.file_edit.text().strip():
            QMessageBox.warning(self, '提示', '请先选择要导入的文件')
            return
        self.accept()

    def get_result(self):
        qd = self.date_edit.date()
        visit_date = date(qd.year(), qd.month(), qd.day())
        return self.file_edit.text().strip(), visit_date


class PatientDetailPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet('''
            QFrame {
                background: #fafafa;
                border: 1px solid #e0e0e0;
                border-radius: 8px;
            }
            QLabel#section_title {
                color: #1565c0;
                font-weight: bold;
                font-size: 13px;
                border-bottom: 1px solid #e0e0e0;
                padding-bottom: 6px;
                margin-top: 8px;
            }
            QLabel#detail_label {
                color: #666;
                font-size: 12px;
            }
            QLabel#detail_value {
                color: #212121;
                font-size: 13px;
            }
            QLabel#name_label {
                color: #1976d2;
                font-size: 22px;
                font-weight: bold;
            }
            QLabel#stage_tag {
                background: #e3f2fd;
                color: #1565c0;
                padding: 3px 10px;
                border-radius: 10px;
                font-size: 12px;
            }
            QLabel#progress_label {
                color: #4caf50;
                font-size: 13px;
                font-weight: bold;
            }
        ''')
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(8)

        self._setup_ui()
        self.clear()

    def _setup_ui(self):
        title = QLabel('患者详情')
        title.setStyleSheet('color: #888; font-size: 12px; margin-bottom: 4px;')
        self._layout.addWidget(title)

        self.name_label = QLabel('')
        self.name_label.setObjectName('name_label')
        self._layout.addWidget(self.name_label)

        self.stage_tag = QLabel('')
        self.stage_tag.setObjectName('stage_tag')
        self.stage_tag.setAlignment(Qt.AlignLeft)
        self._layout.addWidget(self.stage_tag)

        sep1 = QLabel('基本信息')
        sep1.setObjectName('section_title')
        self._layout.addWidget(sep1)

        self.info_layout = QVBoxLayout()
        self.info_layout.setSpacing(6)

        self.phone_row = self._make_info_row('📞 电话', '')
        self.mrn_row = self._make_info_row('📋 病历号', '')
        self.age_row = self._make_info_row('🎂 年龄/性别', '')
        self.plan_row = self._make_info_row('💊 治疗方案', '')
        self.time_row = self._make_info_row('🕐 预约时间', '')

        for row in [self.phone_row, self.mrn_row, self.age_row, self.plan_row, self.time_row]:
            self.info_layout.addLayout(row)
        self._layout.addLayout(self.info_layout)

        sep2 = QLabel('拍照进度')
        sep2.setObjectName('section_title')
        self._layout.addWidget(sep2)

        self.progress_label = QLabel('')
        self.progress_label.setObjectName('progress_label')
        self._layout.addWidget(self.progress_label)

        self.progress_grid = QHBoxLayout()
        self.progress_grid.setSpacing(4)
        self.progress_cells = {}
        for pos in SHOOT_POSITIONS:
            cell = QLabel(pos['name'][0])
            cell.setFixedSize(32, 32)
            cell.setAlignment(Qt.AlignCenter)
            cell.setStyleSheet('''
                QLabel {
                    background: #e0e0e0;
                    color: #9e9e9e;
                    border-radius: 16px;
                    font-size: 13px;
                    font-weight: bold;
                }
            ''')
            cell.setToolTip(pos['name'])
            self.progress_cells[pos['code']] = cell
            self.progress_grid.addWidget(cell)
        self._layout.addLayout(self.progress_grid)

        self._layout.addStretch()

    def _make_info_row(self, label_text: str, value_text: str):
        row = QHBoxLayout()
        row.setSpacing(10)
        label = QLabel(label_text)
        label.setObjectName('detail_label')
        label.setFixedWidth(90)
        value = QLabel(value_text if value_text else '—')
        value.setObjectName('detail_value')
        value.setWordWrap(True)
        row.addWidget(label)
        row.addWidget(value, 1)
        row.value_label = value
        return row

    def _set_row(self, row, value: str):
        row.value_label.setText(value if value else '—')

    def set_patient(self, patient: Patient, visit: Visit):
        self.name_label.setText(patient.name)

        stage_name = next(
            (s['name'] for s in TREATMENT_STAGES if s['code'] == visit.stage_code),
            visit.stage_code
        )
        self.stage_tag.setText(stage_name)

        self._set_row(self.phone_row, patient.phone)
        self._set_row(self.mrn_row, patient.medical_record_number)
        age_gender = ''
        if patient.age:
            age_gender += f'{patient.age}岁'
        if patient.gender:
            age_gender += f'  {patient.gender}'
        self._set_row(self.age_row, age_gender)
        self._set_row(self.plan_row, patient.treatment_plan)
        time_str = visit.get_appointment_display() or '未安排'
        self._set_row(self.time_row, time_str)

        photos = Database.get_visit_photos(visit.id)
        taken_count = sum(1 for p in photos if p.status == PHOTO_STATUS_TAKEN)
        self.progress_label.setText(f'已完成 {taken_count}/{len(SHOOT_POSITIONS)} 个拍摄位')

        photo_by_pos = {p.position_code: p for p in photos}
        for pos in SHOOT_POSITIONS:
            cell = self.progress_cells[pos['code']]
            p = photo_by_pos.get(pos['code'])
            if p and p.status == PHOTO_STATUS_TAKEN:
                cell.setStyleSheet('''
                    QLabel {
                        background: #4caf50;
                        color: white;
                        border-radius: 16px;
                        font-size: 13px;
                        font-weight: bold;
                    }
                ''')
                cell.setToolTip(f'{pos["name"]} ✓ 已拍')
            elif p:
                cell.setStyleSheet('''
                    QLabel {
                        background: #ffcdd2;
                        color: #c62828;
                        border-radius: 16px;
                        font-size: 13px;
                        font-weight: bold;
                    }
                ''')
                cell.setToolTip(f'{pos["name"]} {p.get_status_display()}')
            else:
                cell.setStyleSheet('''
                    QLabel {
                        background: #e0e0e0;
                        color: #9e9e9e;
                        border-radius: 16px;
                        font-size: 13px;
                        font-weight: bold;
                    }
                ''')
                cell.setToolTip(f'{pos["name"]} 待拍')

    def clear(self):
        self.name_label.setText('未选择患者')
        self.stage_tag.setText('请在左侧选择')
        self.stage_tag.setStyleSheet(self.stage_tag.styleSheet())
        for row in [self.phone_row, self.mrn_row, self.age_row, self.plan_row, self.time_row]:
            self._set_row(row, '')
        self.progress_label.setText('请先选择患者')
        for cell in self.progress_cells.values():
            cell.setStyleSheet('''
                QLabel {
                    background: #e0e0e0;
                    color: #9e9e9e;
                    border-radius: 16px;
                    font-size: 13px;
                    font-weight: bold;
                }
            ''')


class MainWindow(QMainWindow):
    start_capture = Signal(int, int)
    start_organize = Signal(int, int)
    start_compare = Signal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle('口腔拍照归档工具')
        self.resize(1180, 760)
        self.current_date = date.today()
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

        header = QLabel('复诊名单')
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header.setFont(header_font)
        left_layout.addWidget(header)

        date_row = QHBoxLayout()
        date_row.setSpacing(6)

        self.today_btn = QPushButton('今天')
        self.tomorrow_btn = QPushButton('明天')
        self.pick_date_btn = QPushButton('📅 选择日期')

        for btn in [self.today_btn, self.tomorrow_btn, self.pick_date_btn]:
            btn.setStyleSheet('''
                QPushButton {
                    background: white;
                    border: 1px solid #ccc;
                    padding: 5px 12px;
                    border-radius: 4px;
                    font-size: 12px;
                }
                QPushButton:hover { background: #f0f0f0; }
                QPushButton:checked {
                    background: #1976d2;
                    color: white;
                    border-color: #1976d2;
                }
            ''')
            btn.setCheckable(True)

        self.date_display = QLabel('')
        self.date_display.setStyleSheet('color: #1976d2; font-weight: bold; font-size: 14px;')
        self.date_display.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.today_btn.clicked.connect(lambda: self._change_date(date.today()))
        self.tomorrow_btn.clicked.connect(lambda: self._change_date(date.today() + timedelta(days=1)))
        self.pick_date_btn.clicked.connect(self._on_pick_date)

        date_row.addWidget(self.today_btn)
        date_row.addWidget(self.tomorrow_btn)
        date_row.addWidget(self.pick_date_btn)
        date_row.addWidget(self.date_display, 1)
        left_layout.addLayout(date_row)

        import_row = QHBoxLayout()
        self.import_btn = QPushButton('📥 导入预约')
        self.import_btn.setStyleSheet('''
            QPushButton {
                background: #2e7d32;
                color: white;
                border: none;
                padding: 8px 14px;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1b5e20; }
        ''')
        self.import_btn.clicked.connect(self._on_import_csv)
        import_row.addWidget(self.import_btn)

        self.add_btn = QPushButton('+ 新增患者')
        self.add_btn.setStyleSheet('''
            QPushButton {
                background: #1976d2;
                color: white;
                border: none;
                padding: 8px 14px;
                border-radius: 5px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background: #1565c0; }
        ''')
        self.add_btn.clicked.connect(self._on_add_patient)
        import_row.addWidget(self.add_btn)

        self.refresh_btn = QPushButton('⟳ 刷新')
        self.refresh_btn.setStyleSheet('''
            QPushButton {
                background: #78909c;
                color: white;
                border: none;
                padding: 8px 14px;
                border-radius: 5px;
                font-size: 13px;
            }
            QPushButton:hover { background: #546e7a; }
        ''')
        self.refresh_btn.clicked.connect(self._load_visit_list)
        import_row.addWidget(self.refresh_btn)
        left_layout.addLayout(import_row)

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
                padding: 8px 12px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background: #e3f2fd;
                color: #1565c0;
            }
        ''')
        left_layout.addWidget(self.visit_list, 1)

        self.total_label = QLabel('')
        self.total_label.setStyleSheet('color: #666; font-size: 12px; padding: 4px 2px;')
        left_layout.addWidget(self.total_label)

        main_layout.addWidget(left_panel, 2)

        middle_panel = QWidget()
        middle_layout = QVBoxLayout(middle_panel)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(12)

        self.detail_panel = PatientDetailPanel()
        middle_layout.addWidget(self.detail_panel, 1)

        main_layout.addWidget(middle_panel, 2)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)

        title = QLabel('操作')
        title_font = QFont()
        title_font.setPointSize(18)
        title_font.setBold(True)
        title.setFont(title_font)
        right_layout.addWidget(title)

        self.selected_patient_label = QLabel('请先在左侧选择患者')
        self.selected_patient_label.setStyleSheet('color: #888; font-size: 13px;')
        self.selected_patient_label.setWordWrap(True)
        right_layout.addWidget(self.selected_patient_label)

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
        main_layout.addWidget(right_panel, 2)

        self._set_buttons_enabled(False)
        self._update_date_buttons()

    def _style_large_button(self, btn, color):
        btn.setMinimumHeight(72)
        btn.setStyleSheet(f'''
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 18px;
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

    def _update_date_buttons(self):
        today = date.today()
        tomorrow = today + timedelta(days=1)
        self.today_btn.setChecked(self.current_date == today)
        self.tomorrow_btn.setChecked(self.current_date == tomorrow)
        self.pick_date_btn.setChecked(self.current_date not in (today, tomorrow))

        weekday_names = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
        wd = weekday_names[self.current_date.weekday()]
        prefix = ''
        if self.current_date == today:
            prefix = '今天 · '
        elif self.current_date == tomorrow:
            prefix = '明天 · '
        self.date_display.setText(f'{prefix}{self.current_date.strftime("%Y-%m-%d")} {wd}')

    def _change_date(self, d: date):
        if self.current_date != d:
            self.current_date = d
            self._update_date_buttons()
            self._load_visit_list()

    def _on_pick_date(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('选择日期')
        layout = QVBoxLayout(dialog)

        date_edit = QDateEdit()
        date_edit.setCalendarPopup(True)
        date_edit.setDisplayFormat('yyyy-MM-dd  dddd')
        date_edit.setDate(QDate(self.current_date.year, self.current_date.month, self.current_date.day))
        date_edit.setMinimumDate(QDate(2020, 1, 1))
        date_edit.setMaximumDate(QDate(2035, 12, 31))
        layout.addWidget(date_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() == QDialog.Accepted:
            qd = date_edit.date()
            self._change_date(date(qd.year(), qd.month(), qd.day()))

    def _add_group_header(self, title: str, count: int):
        item = QListWidgetItem(f'  {title}  ({count}人)')
        item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
        item.setBackground(QColor('#f5f7fa'))
        f = QFont()
        f.setBold(True)
        f.setPointSize(11)
        item.setFont(f)
        item.setForeground(QColor('#546e7a'))
        self.visit_list.addItem(item)

    def _add_patient_item(self, patient: Patient, visit: Visit):
        time_display = visit.get_appointment_display()
        if time_display:
            time_text = f'🕐 {time_display}  '
        else:
            time_text = '⏱ 未安排  '

        item_text = f'{time_text}{patient.name}'

        identifier = patient.get_display_identifier()
        if identifier:
            item_text += f'\n      {identifier}'

        stage_name = next(
            (s['name'] for s in TREATMENT_STAGES if s['code'] == visit.stage_code),
            visit.stage_code
        )
        item_text += f'  ·  {stage_name}'

        photos = Database.get_visit_photos(visit.id)
        taken = sum(1 for p in photos if p.status == PHOTO_STATUS_TAKEN)
        if taken > 0:
            item_text += f'  [{taken}/5 ✓]'

        item = QListWidgetItem(item_text)
        item.setData(Qt.UserRole, (patient.id, visit.id))

        if not time_display:
            item.setForeground(QColor('#999'))

        self.visit_list.addItem(item)
        self.patient_visits[(patient.id, visit.id)] = (patient, visit)

    def _load_visit_list(self):
        try:
            self.visit_list.clear()
            self.patient_visits.clear()
            self._set_buttons_enabled(False)
            self.detail_panel.clear()
            self.selected_patient_label.setText('请先在左侧选择患者')

            visits = Database.get_today_visits(self.current_date)

            if not visits:
                item = QListWidgetItem('📋  当前日期暂无复诊患者\n点击「导入预约」从表格导入，或点击「+ 新增患者」添加')
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
                item.setTextAlignment(Qt.AlignCenter)
                f = QFont()
                f.setPointSize(12)
                item.setFont(f)
                item.setForeground(QColor('#888'))
                self.visit_list.addItem(item)
                self.total_label.setText('共 0 位患者')
                return

            morning = []
            afternoon = []
            unscheduled = []

            for patient, visit in visits:
                if visit.appointment_time is None:
                    unscheduled.append((patient, visit))
                elif visit.appointment_time.hour < 12:
                    morning.append((patient, visit))
                else:
                    afternoon.append((patient, visit))

            if morning:
                self._add_group_header('🌅 上午', len(morning))
                for patient, visit in morning:
                    self._add_patient_item(patient, visit)

            if afternoon:
                self._add_group_header('🌆 下午', len(afternoon))
                for patient, visit in afternoon:
                    self._add_patient_item(patient, visit)

            if unscheduled:
                self._add_group_header('⏱ 未安排时间', len(unscheduled))
                for patient, visit in unscheduled:
                    self._add_patient_item(patient, visit)

            total = len(visits)
            self.total_label.setText(
                f'共 {total} 位患者  ·  上午 {len(morning)} 人  ·  下午 {len(afternoon)} 人  ·  未安排 {len(unscheduled)} 人'
            )

        except Exception as e:
            print(f"Load visit list error: {e}")
            import traceback
            traceback.print_exc()
            self.visit_list.clear()
            item = QListWidgetItem(f'❌ 加载失败：{str(e)}\n请点击「刷新」重试')
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setTextAlignment(Qt.AlignCenter)
            self.visit_list.addItem(item)
            self.total_label.setText('加载失败')

    def _on_import_csv(self):
        dialog = ImportDialog(self.current_date, self)
        if dialog.exec() != QDialog.Accepted:
            return

        file_path, target_date = dialog.get_result()
        if not file_path or not os.path.exists(file_path):
            return

        try:
            result: ImportResult = Database.import_appointments(file_path, target_date)
        except Exception as e:
            QMessageBox.critical(self, '导入失败', f'导入过程中发生错误：\n{str(e)}')
            return

        if target_date != self.current_date:
            reply = QMessageBox.question(
                self, '切换日期',
                f'已导入到 {target_date.isoformat()}，是否切换到该日期查看？',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )
            if reply == QMessageBox.Yes:
                self.current_date = target_date
                self._update_date_buttons()

        try:
            self._load_visit_list()
        except Exception as e:
            QMessageBox.warning(self, '刷新失败', f'数据已导入，但列表刷新失败：\n{str(e)}')

        self._show_import_result(result, target_date)

    def _show_import_result(self, result: ImportResult, target_date: date):
        date_str = target_date.strftime('%Y-%m-%d')
        parts = [f'导入日期：{date_str}\n']

        if result.total_imported > 0:
            parts.append(f'✅ 成功导入 {result.total_imported} 条预约：')
            for line in result.imported[:10]:
                parts.append(f'   · {line}')
            if len(result.imported) > 10:
                parts.append(f'   ... 还有 {len(result.imported) - 10} 条')
            parts.append('')

        if result.total_skipped > 0:
            parts.append(f'⏭ 跳过 {result.total_skipped} 条（同日已有预约）：')
            for line in result.skipped_duplicate[:10]:
                parts.append(f'   · {line}')
            if len(result.skipped_duplicate) > 10:
                parts.append(f'   ... 还有 {len(result.skipped_duplicate) - 10} 条')
            parts.append('')

        if result.total_errors > 0:
            parts.append(f'❌ 格式错误 {result.total_errors} 条：')
            for line in result.errors[:10]:
                parts.append(f'   · {line}')
            if len(result.errors) > 10:
                parts.append(f'   ... 还有 {len(result.errors) - 10} 条')

        msg = '\n'.join(parts)

        if result.total_imported > 0 and result.total_skipped == 0 and result.total_errors == 0:
            QMessageBox.information(self, '导入完成', msg)
        elif result.total_imported > 0 or result.total_skipped > 0:
            if result.total_errors > 0:
                QMessageBox.warning(self, '导入完成（存在问题）', msg)
            else:
                QMessageBox.information(self, '导入完成', msg)
        else:
            QMessageBox.warning(self, '导入完成', msg or '没有可导入的预约')

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
        dialog = AddPatientDialog(self.current_date, self)
        if dialog.exec() == QDialog.Accepted:
            patient, stage_code, appointment_time, visit_date = dialog.get_patient_data()

            if not patient.name:
                QMessageBox.warning(self, '提示', '请输入患者姓名')
                return

            patient_id = Database.add_patient(patient)
            visit = Visit(
                patient_id=patient_id,
                visit_date=visit_date,
                appointment_time=appointment_time,
                stage_code=stage_code
            )
            visit_id = Database.add_visit(visit)

            if visit_date != self.current_date:
                reply = QMessageBox.question(
                    self, '切换日期',
                    f'已添加到 {visit_date.isoformat()}，是否切换到该日期？',
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.Yes:
                    self.current_date = visit_date
                    self._update_date_buttons()

            self._load_visit_list()
            QMessageBox.information(self, '成功', f'已添加患者：{patient.name}')

    def showEvent(self, event):
        self._load_visit_list()
        super().showEvent(event)

    def on_visit_selection_changed(self):
        item = self.visit_list.currentItem()
        data = item.data(Qt.UserRole) if item else None

        has_selection = data is not None
        self._set_buttons_enabled(has_selection)

        if has_selection and data in self.patient_visits:
            patient, visit = self.patient_visits[data]
            self.detail_panel.set_patient(patient, visit)

            stage_name = next(
                (s['name'] for s in TREATMENT_STAGES if s['code'] == visit.stage_code),
                visit.stage_code
            )
            time_str = visit.get_appointment_display() or '未安排'
            self.selected_patient_label.setText(
                f'已选择：{patient.name}\n'
                f'{stage_name}  ·  {time_str}'
            )
        else:
            self.detail_panel.clear()
            self.selected_patient_label.setText('请先在左侧选择患者')

    def on_subwindow_closed(self):
        self._load_visit_list()
