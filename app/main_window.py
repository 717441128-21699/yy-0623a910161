from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QHBoxLayout, QLineEdit, QMessageBox, QDialog,
    QComboBox, QSpinBox, QDialogButtonBox, QHeaderView, QTableWidget, QTableWidgetItem
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from datetime import date

from .database import Database
from .models import Patient, Visit, TREATMENT_STAGES


class AddPatientDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('新增患者')
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)

        form_layout = QVBoxLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText('患者姓名')
        form_layout.addWidget(self.name_edit)

        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText('联系电话')
        form_layout.addWidget(self.phone_edit)

        age_layout = QHBoxLayout()
        self.age_spin = QSpinBox()
        self.age_spin.setRange(0, 100)
        self.age_spin.setPrefix('年龄: ')
        age_layout.addWidget(self.age_spin)

        self.gender_combo = QComboBox()
        self.gender_combo.addItems(['', '男', '女'])
        self.gender_combo.setPlaceholderText('性别')
        age_layout.addWidget(self.gender_combo)
        form_layout.addLayout(age_layout)

        self.plan_edit = QLineEdit()
        self.plan_edit.setPlaceholderText('治疗方案（如：正畸、种植）')
        form_layout.addWidget(self.plan_edit)

        stage_layout = QHBoxLayout()
        stage_label = QLabel('疗程阶段:')
        self.stage_combo = QComboBox()
        for stage in TREATMENT_STAGES:
            self.stage_combo.addItem(stage['name'], stage['code'])
        stage_layout.addWidget(stage_label)
        stage_layout.addWidget(self.stage_combo)
        form_layout.addLayout(stage_layout)

        layout.addLayout(form_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_patient_data(self):
        return Patient(
            name=self.name_edit.text().strip(),
            phone=self.phone_edit.text().strip(),
            age=self.age_spin.value() if self.age_spin.value() > 0 else None,
            gender=self.gender_combo.currentText(),
            treatment_plan=self.plan_edit.text().strip()
        ), self.stage_combo.currentData()


class MainWindow(QMainWindow):
    start_capture = Signal(int, int)
    start_organize = Signal(int, int)
    start_compare = Signal(int)

    def __init__(self):
        super().__init__()
        self.setWindowTitle('口腔拍照归档工具')
        self.resize(1000, 700)
        self.patient_visits = {}
        self._init_ui()
        self._load_visit_list()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)

        header = QLabel(f"今日复诊名单")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header.setFont(header_font)
        left_layout.addWidget(header)

        date_label = QLabel(date.today().strftime('%Y年%m月%d日'))
        date_label.setStyleSheet('color: #666;')
        left_layout.addWidget(date_label)

        self.visit_list = QListWidget()
        self.visit_list.itemDoubleClicked.connect(self._on_visit_double_clicked)
        self.visit_list.itemSelectionChanged.connect(self.on_visit_selection_changed)
        self.visit_list.setStyleSheet('''
            QListWidget {
                border: 1px solid #ddd;
                border-radius: 8px;
                background: white;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #f0f0f0;
            }
            QListWidget::item:selected {
                background: #e3f2fd;
                color: #1565c0;
            }
        ''')
        left_layout.addWidget(self.visit_list, 1)

        add_btn = QPushButton('+ 新增患者')
        add_btn.setStyleSheet('''
            QPushButton {
                background: #1976d2;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 6px;
                font-size: 14px;
            }
            QPushButton:hover {
                background: #1565c0;
            }
        ''')
        add_btn.clicked.connect(self._on_add_patient)
        left_layout.addWidget(add_btn)

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
            item = QListWidgetItem('暂无今日复诊患者')
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            self.visit_list.addItem(item)
            return

        for patient, visit in visits:
            stage_name = next(
                (s['name'] for s in TREATMENT_STAGES if s['code'] == visit.stage_code),
                visit.stage_code
            )
            item_text = f"{patient.name}  |  {stage_name}"
            if patient.age:
                item_text += f"  |  {patient.age}岁"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, (patient.id, visit.id))
            self.visit_list.addItem(item)

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
            patient, stage_code = dialog.get_patient_data()

            if not patient.name:
                QMessageBox.warning(self, '提示', '请输入患者姓名')
                return

            patient_id = Database.add_patient(patient)
            visit = Visit(
                patient_id=patient_id,
                visit_date=date.today(),
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
