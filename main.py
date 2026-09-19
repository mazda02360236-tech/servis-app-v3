import sys
import os
import sqlite3
import urllib.request
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QDateEdit, QComboBox
)
from PyQt6.QtCore import QDate

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def setup_cyrillic_font():
    """Використовує системний шрифт Arial для коректного відображення кирилиці в PDF."""
    win_font_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'arial.ttf')
    
    if os.path.exists(win_font_path):
        try:
            pdfmetrics.registerFont(TTFont('ArialWin', win_font_path))
            return 'ArialWin'
        except Exception:
            pass

    font_path = "Roboto-Regular.ttf"
    if not os.path.exists(font_path):
        try:
            url = "https://raw.githubusercontent.com/google/fonts/main/apache/roboto/static/Roboto-Regular.ttf"
            urllib.request.urlretrieve(url, font_path)
        except Exception:
            pass

    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont('Roboto', font_path))
            return 'Roboto'
        except Exception:
            pass

    return 'Helvetica'

class ServiceManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Облік ремонту інструменту та обладнання")
        self.setGeometry(100, 100, 1100, 680)
        
        self.font_name = setup_cyrillic_font()
        self.init_db()
        self.init_ui()

    def init_db(self):
        app_data_dir = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'ServiceManager')
        os.makedirs(app_data_dir, exist_ok=True)
        
        db_path = os.path.join(app_data_dir, "service_orders.db")
        
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT,
                phone TEXT,
                date_in TEXT,
                date_out TEXT,
                item_name TEXT,
                serial_num TEXT,
                equipment TEXT,
                issue TEXT,
                status TEXT
            )
        """)
        self.conn.commit()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        form_layout = QVBoxLayout()

        r1 = QHBoxLayout()
        self.client_input = QLineEdit()
        self.client_input.setPlaceholderText("ПІБ Клієнта")
        self.phone_input = QLineEdit()
        self.phone_input.setPlaceholderText("Телефон клієнта")
        r1.addWidget(QLabel("Клієнт:"))
        r1.addWidget(self.client_input)
        r1.addWidget(QLabel("Телефон:"))
        r1.addWidget(self.phone_input)
        form_layout.addLayout(r1)

        r2 = QHBoxLayout()
        self.item_input = QLineEdit()
        self.item_input.setPlaceholderText("Назва товару / інструменту")
        self.serial_input = QLineEdit()
        self.serial_input.setPlaceholderText("Серійний номер")
        self.equipment_input = QLineEdit()
        self.equipment_input.setPlaceholderText("Кейс, акумулятор тощо")
        r2.addWidget(QLabel("Товар:"))
        r2.addWidget(self.item_input)
        r2.addWidget(QLabel("Серійний №:"))
        r2.addWidget(self.serial_input)
        r2.addWidget(QLabel("Комплектація:"))
        r2.addWidget(self.equipment_input)
        form_layout.addLayout(r2)

        r3 = QHBoxLayout()
        self.date_in_edit = QDateEdit()
        self.date_in_edit.setDate(QDate.currentDate())
        self.date_in_edit.setCalendarPopup(True)

        self.date_out_edit = QDateEdit()
        self.date_out_edit.setDate(QDate.currentDate())
        self.date_out_edit.setCalendarPopup(True)

        self.status_box = QComboBox()
        self.status_box.addItems(["В роботі", "Очікує запчастин", "Готово", "Видано"])

        r3.addWidget(QLabel("Дата прийому:"))
        r3.addWidget(self.date_in_edit)
        r3.addWidget(QLabel("Дата видачі:"))
        r3.addWidget(self.date_out_edit)
        r3.addWidget(QLabel("Статус:"))
        r3.addWidget(self.status_box)
        form_layout.addLayout(r3)

        r4 = QHBoxLayout()
        self.issue_input = QLineEdit()
        self.issue_input.setPlaceholderText("Опис несправності")
        r4.addWidget(QLabel("Несправність:"))
        r4.addWidget(self.issue_input)
        form_layout.addLayout(r4)

        main_layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        save_btn = QPushButton("Зберегти замовлення")
        save_btn.clicked.connect(self.save_order)
        
        print_btn = QPushButton("Сформувати та роздрукувати квитанцію")
        print_btn.clicked.connect(self.print_receipt)

        delete_btn = QPushButton("Видалити замовлення")
        delete_btn.clicked.connect(self.delete_order)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(print_btn)
        btn_layout.addWidget(delete_btn)
        main_layout.addLayout(btn_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(10)
        self.table.setHorizontalHeaderLabels([
            "ID", "Клієнт", "Телефон", "Дата прийому", "Дата видачі", 
            "Товар", "Серійний №", "Комплектація", "Несправність", "Статус"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.fill_form_from_table)
        main_layout.addWidget(self.table)

        self.load_orders()

    def save_order(self):
        client = self.client_input.text().strip()
        phone = self.phone_input.text().strip()
        date_in = self.date_in_edit.date().toString("yyyy-MM-dd")
        date_out = self.date_out_edit.date().toString("yyyy-MM-dd")
        item = self.item_input.text().strip()
        serial = self.serial_input.text().strip()
        equipment = self.equipment_input.text().strip()
        issue = self.issue_input.text().strip()
        status = self.status_box.currentText()

        if not client or not item:
            QMessageBox.warning(self, "Помилка", "Заповніть обов'язкові поля!")
            return

        self.cursor.execute("""
            INSERT INTO orders (client_name, phone, date_in, date_out, item_name, serial_num, equipment, issue, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (client, phone, date_in, date_out, item, serial, equipment, issue, status))
        self.conn.commit()

        self.clear_fields()
        self.load_orders()
        QMessageBox.information(self, "Успіх", "Замовлення збережено!")

    def load_orders(self):
        self.table.setRowCount(0)
        self.cursor.execute("SELECT * FROM orders")
        rows = self.cursor.fetchall()
        for row_idx, row_data in enumerate(rows):
            self.table.insertRow(row_idx)
            for col_idx, value in enumerate(row_data):
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(str(value if value else "")))

    def fill_form_from_table(self):
        selected_row = self.table.currentRow()
        if selected_row >= 0:
            self.client_input.setText(self.table.item(selected_row, 1).text())
            self.phone_input.setText(self.table.item(selected_row, 2).text())
            self.item_input.setText(self.table.item(selected_row, 5).text())
            self.serial_input.setText(self.table.item(selected_row, 6).text())
            self.equipment_input.setText(self.table.item(selected_row, 7).text())
            self.issue_input.setText(self.table.item(selected_row, 8).text())

    def clear_fields(self):
        self.client_input.clear()
        self.phone_input.clear()
        self.item_input.clear()
        self.serial_input.clear()
        self.equipment_input.clear()
        self.issue_input.clear()

    def delete_order(self):
        selected_row = self.table.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "Помилка", "Оберіть рядок!")
            return

        order_id = self.table.item(selected_row, 0).text()
        self.cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        self.conn.commit()
        self.load_orders()
        self.clear_fields()

    def print_receipt(self):
        selected_row = self.table.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "Помилка", "Оберіть замовлення зі списку!")
            return

        order_id = self.table.item(selected_row, 0).text()
        client = self.table.item(selected_row, 1).text()
        phone = self.table.item(selected_row, 2).text()
        date_in = self.table.item(selected_row, 3).text()
        date_out = self.table.item(selected_row, 4).text()
        item = self.table.item(selected_row, 5).text()
        serial = self.table.item(selected_row, 6).text()
        equipment = self.table.item(selected_row, 7).text()
        issue = self.table.item(selected_row, 8).text()
        status = self.table.item(selected_row, 9).text()

        pdf_filename = f"Квитанция_Заказ_{order_id}.pdf"
        
        c = canvas.Canvas(pdf_filename, pagesize=letter)
        c.setFont(self.font_name, 16)
        c.drawString(100, 750, f"АКТ-КВИТАНЦІЯ РЕМОНТУ № {order_id}")
        
        c.setFont(self.font_name, 11)
        c.drawString(100, 710, f"Дата прийому: {date_in}   |   Планова дата видачі: {date_out}")
        c.drawString(100, 685, f"Клієнт: {client}")
        c.drawString(100, 665, f"Телефон: {phone}")
        c.drawString(100, 640, f"Товар / Модель: {item}")
        c.drawString(100, 620, f"Серійний номер: {serial}")
        c.drawString(100, 600, f"Комплектація: {equipment}")
        c.drawString(100, 575, f"Опис несправності: {issue}")
        c.drawString(100, 550, f"Поточний статус: {status}")

        c.line(100, 520, 500, 520)
        c.drawString(100, 480, "Підпис клієнта: __________________")
        c.drawString(100, 450, "Підпис майстра: __________________")

        c.save()

        if sys.platform == "win32":
            os.startfile(pdf_filename)
        else:
            QMessageBox.information(self, "Успіх", f"Квитанцію збережено в файл {pdf_filename}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ServiceManagerApp()
    window.show()
    sys.exit(app.exec())
