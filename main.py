import sys
import os
import sqlite3
import shutil
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QPushButton, QTableWidget,
    QTableWidgetItem, QComboBox, QDateEdit, QMessageBox, QFileDialog,
    QDialog, QScrollArea
)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QPixmap

# --- НАЛАШТУВАННЯ ПАПКИ ДЛЯ ФОТО ---
UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# --- РОБОТА З БАЗОЮ ДАНИХ ---
def init_db():
    conn = sqlite3.connect("service_center.db")
    cursor = conn.cursor()
    
    # Таблиця заявок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_name TEXT,
            phone TEXT,
            device TEXT,
            equipment TEXT,
            problem TEXT,
            date_in TEXT,
            date_out TEXT,
            status TEXT,
            cost REAL
        )
    ''')
    
    # Таблиця для фотографій заявок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER,
            photo_path TEXT,
            FOREIGN KEY (request_id) REFERENCES requests (id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

# --- ДІАЛОГ ПЕРЕГЛЯДУ ФОТОГРАФІЙ ---
class PhotoViewerDialog(QDialog):
    def __init__(self, photo_paths, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Прикріплені фотографії")
        self.resize(600, 500)
        
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        scroll_layout = QVBoxLayout(content_widget)
        
        if not photo_paths:
            scroll_layout.addWidget(QLabel("До цієї заявки немає доданих фотографій."))
        else:
            for path in photo_paths:
                if os.path.exists(path):
                    lbl = QLabel()
                    pixmap = QPixmap(path)
                    lbl.setPixmap(pixmap.scaledToWidth(500, Qt.TransformationMode.SmoothTransformation))
                    scroll_layout.addWidget(lbl)
                else:
                    scroll_layout.addWidget(QLabel(f"Файл не знайдено: {path}"))
                    
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        btn_close = QPushButton("Закрити")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

# --- ГОЛОВНЕ ВІКНО ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Система обліку сервісного центру")
        self.resize(1000, 700)
        
        self.selected_photos = []  # Тимчасовий список обраних фото під час створення
        
        init_db()
        self.init_ui()
        self.load_requests()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- ФОРМА ВВОДУ ---
        form_layout = QVBoxLayout()

        # Рядок 1: Клієнт, Телефон, Пристрій
        r1 = QHBoxLayout()
        self.client_input = QLineEdit()
        self.client_input.setPlaceholderText("ПІБ Клієнта")
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Номер телефону")
        self.device_input = QLineEdit()
        self.device_input.setPlaceholderText("Пристрій (модель)")
        
        r1.addWidget(QLabel("Клієнт:"))
        r1.addWidget(self.client_input)
        r1.addWidget(QLabel("Телефон:"))
        r1.addWidget(self.phone_input)
        r1.addWidget(QLabel("Пристрій:"))
        r1.addWidget(self.device_input)
        form_layout.addLayout(r1)

        # Рядок 2: Комплектація та Опис проблеми
        r2 = QHBoxLayout()
        self.equipment_input = QLineEdit()
        self.equipment_input.setPlaceholderText("Комплектація (зарядка, чохол...)")
        self.problem_input = QLineEdit()
        self.problem_input.setPlaceholderText("Несправність / Опис проблеми")
        
        r2.addWidget(QLabel("Комплектація:"))
        r2.addWidget(self.equipment_input)
        r2.addWidget(QLabel("Проблема:"))
        r2.addWidget(self.problem_input)
        form_layout.addLayout(r2)

        # Рядок 3: Дати, Статус, Вартість
        r3 = QHBoxLayout()
        self.date_in_edit = QDateEdit()
        self.date_in_edit.setDate(QDate.currentDate())
        self.date_in_edit.setCalendarPopup(True)

        self.date_out_edit = QDateEdit()
        self.date_out_edit.setDate(QDate.currentDate())
        self.date_out_edit.setCalendarPopup(True)

        self.status_box = QComboBox()
        self.status_box.addItems(["В роботі", "Очікує запчастин", "Готово", "Видано"])

        self.cost_input = QLineEdit()
        self.cost_input.setPlaceholderText("0.00")

        r3.addWidget(QLabel("Дата прийому:"))
        r3.addWidget(self.date_in_edit)
        r3.addWidget(QLabel("Дата видачі:"))
        r3.addWidget(self.date_out_edit)
        r3.addWidget(QLabel("Статус:"))
        r3.addWidget(self.status_box)
        r3.addWidget(QLabel("Ціна (грн):"))
        r3.addWidget(self.cost_input)
        form_layout.addLayout(r3)

        # Рядок 4: Додавання фото
        r4 = QHBoxLayout()
        self.btn_add_photo = QPushButton("📷 Додати фото")
        self.btn_add_photo.clicked.connect(self.select_photos)
        self.lbl_photo_count = QLabel("Обрано фото: 0")
        
        r4.addWidget(self.btn_add_photo)
        r4.addWidget(self.lbl_photo_count)
        r4.addStretch()
        form_layout.addLayout(r4)

        # Кнопки дій
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Створити заявку")
        self.btn_save.clicked.connect(self.add_request)
        self.btn_view_photo = QPushButton("🖼️ Переглянути фото обраної заявки")
        self.btn_view_photo.clicked.connect(self.view_selected_photos)
        
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_view_photo)
        form_layout.addLayout(btn_layout)

        main_layout.addLayout(form_layout)

        # --- ТАБЛИЦЯ ЗАЯВОК ---
        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "ID", "Клієнт", "Телефон", "Пристрій", "Комплектація", 
            "Проблема", "Дата прийому", "Дата видачі", "Статус", "Ціна", "Фото"
        ])
        main_layout.addWidget(self.table)

    def select_photos(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Оберіть фотографії", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if files:
            self.selected_photos = files
            self.lbl_photo_count.setText(f"Обрано фото: {len(files)}")

    def add_request(self):
        client = self.client_input.text().strip()
        phone = self.phone_input.text().strip()
        device = self.device_input.text().strip()
        equipment = self.equipment_input.text().strip()
        problem = self.problem_input.text().strip()
        date_in = self.date_in_edit.date().toString("yyyy-MM-dd")
        date_out = self.date_out_edit.date().toString("yyyy-MM-dd")
        status = self.status_box.currentText()
        cost = self.cost_input.text().strip() or "0"

        if not client or not device:
            QMessageBox.warning(self, "Помилка", "Заповніть обов'язкові поля (Клієнт, Пристрій)!")
            return

        conn = sqlite3.connect("service_center.db")
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO requests (client_name, phone, device, equipment, problem, date_in, date_out, status, cost)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (client, phone, device, equipment, problem, date_in, date_out, status, cost))
        
        request_id = cursor.lastrowid

        # Збереження фотографій у локальну папку та БД
        for photo_path in self.selected_photos:
            if os.path.exists(photo_path):
                ext = os.path.splitext(photo_path)[1]
                new_filename = f"req_{request_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{ext}"
                dest_path = os.path.join(UPLOAD_DIR, new_filename)
                
                shutil.copy(photo_path, dest_path)
                
                cursor.execute('''
                    INSERT INTO photos (request_id, photo_path)
                    VALUES (?, ?)
                ''', (request_id, dest_path))

        conn.commit()
        conn.close()

        QMessageBox.information(self, "Успіх", "Заявку успішно створено!")
        self.clear_form()
        self.load_requests()

    def clear_form(self):
        self.client_input.clear()
        self.phone_input.clear()
        self.device_input.clear()
        self.equipment_input.clear()
        self.problem_input.clear()
        self.cost_input.clear()
        self.selected_photos = []
        self.lbl_photo_count.setText("Обрано фото: 0")

    def load_requests(self):
        conn = sqlite3.connect("service_center.db")
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM requests ORDER BY id DESC")
        rows = cursor.fetchall()
        
        self.table.setRowCount(0)
        for row_idx, row_data in enumerate(rows):
            self.table.insertRow(row_idx)
            for col_idx, value in enumerate(row_data):
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))
            
            # Отримуємо кількість фото для цієї заявки
            req_id = row_data[0]
            cursor.execute("SELECT COUNT(*) FROM photos WHERE request_id = ?", (req_id,))
            photo_count = cursor.fetchone()[0]
            self.table.setItem(row_idx, 10, QTableWidgetItem(f"📷 ({photo_count})"))

        conn.close()

    def view_selected_photos(self):
        current_row = self.table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "Увага", "Будь ласка, виберіть заявку в таблиці!")
            return

        request_id = int(self.table.item(current_row, 0).text())

        conn = sqlite3.connect("service_center.db")
        cursor = conn.cursor()
        cursor.execute("SELECT photo_path FROM photos WHERE request_id = ?", (request_id,))
        photos = [row[0] for row in cursor.fetchall()]
        conn.close()

        dialog = PhotoViewerDialog(photos, self)
        dialog.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
