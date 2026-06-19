import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from app.database import Database
from app.main_window import MainWindow
from app.capture_window import CaptureWindow
from app.organize_window import OrganizeWindow
from app.compare_window import CompareWindow


class Application:
    def __init__(self):
        Database.init()

        self.app = QApplication(sys.argv)
        self.app.setApplicationName('口腔拍照归档工具')
        self.app.setStyle('Fusion')

        default_font = QFont('Microsoft YaHei', 10)
        self.app.setFont(default_font)

        self.main_window = MainWindow()
        self.main_window.start_capture.connect(self.open_capture_window)
        self.main_window.start_organize.connect(self.open_organize_window)
        self.main_window.start_compare.connect(self.open_compare_window)

        self.current_subwindow = None

    def open_capture_window(self, patient_id: int, visit_id: int):
        self.current_subwindow = CaptureWindow(patient_id, visit_id, self.main_window)
        self.current_subwindow.capture_finished.connect(self.on_subwindow_closed)
        self.current_subwindow.show()

    def open_organize_window(self, patient_id: int, visit_id: int):
        self.current_subwindow = OrganizeWindow(patient_id, visit_id, self.main_window)
        self.current_subwindow.organize_finished.connect(self.on_subwindow_closed)
        self.current_subwindow.show()

    def open_compare_window(self, patient_id: int):
        self.current_subwindow = CompareWindow(patient_id, self.main_window)
        self.current_subwindow.compare_finished.connect(self.on_subwindow_closed)
        self.current_subwindow.show()

    def on_subwindow_closed(self):
        self.main_window.on_subwindow_closed()
        self.current_subwindow = None

    def run(self):
        self.main_window.show()
        sys.exit(self.app.exec())


def main():
    app = Application()
    app.run()


if __name__ == '__main__':
    main()
