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

from reportlab.lib.pagesizes import A5, landscape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors

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
        self.setGeometry(100, 100, 1100, 720)
        
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
        self.date_out_edit.setDate(QDate.currentDate().addMonths(3))
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
        
        print_btn = QPushButton("Сформувати та роздрукувати квитанцію (А5)")
        print_btn.clicked.connect(self.print_receipt)

        delete_btn = QPushButton("Видалити замовлення")
        delete_btn.clicked.connect(self.delete_order)

        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(print_btn)
        btn_layout.addWidget(delete_btn)
        main_layout.addLayout(btn_layout)

        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Пошук (ПІБ або Телефон):")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введіть ім'я або номер телефону для фільтрації...")
        self.search_input.textChanged.connect(self.search_orders)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        main_layout.addLayout(search_layout)

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
            QMessageBox.warning(self, "Помилка", "Заповніть обов'язкові поля (Клієнт та Товар)!")
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

    def search_orders(self):
        query = self.search_input.text().strip()
        self.table.setRowCount(0)
        
        if not query:
            self.cursor.execute("SELECT * FROM orders")
        else:
            search_pattern = f"%{query}%"
            self.cursor.execute("""
                SELECT * FROM orders 
                WHERE client_name LIKE ? OR phone LIKE ?
            """, (search_pattern, search_pattern))
            
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
            
            date_in_str = self.table.item(selected_row, 3).text()
            if date_in_str:
                self.date_in_edit.setDate(QDate.fromString(date_in_str, "yyyy-MM-dd"))
            
            date_out_str = self.table.item(selected_row, 4).text()
            if date_out_str:
                self.date_out_edit.setDate(QDate.fromString(date_out_str, "yyyy-MM-dd"))

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
        self.search_input.clear()
        self.date_in_edit.setDate(QDate.currentDate())
        self.date_out_edit.setDate(QDate.currentDate().addMonths(3))

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
            QMessageBox.warning(self, "Увага", "Будь ласка, оберіть замовлення зі списку таблиці!")
            return

        try:
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

            docs_dir = os.path.join(os.path.expanduser('~'), 'Documents')
            pdf_filename = os.path.join(docs_dir, f"Квитанция_A5_{order_id}.pdf")
            
            # Створення документа у форматі А5 Альбомний (595 x 420 pt)
            c = canvas.Canvas(pdf_filename, pagesize=landscape(A5))
            width, height = landscape(A5)

            # Зовнішня декоративна рамка
            c.setStrokeColor(colors.HexColor("#2C3E50"))
            c.setLineWidth(1.5)
            c.rect(15, 15, width - 30, height - 30)

            # Верхній заголовок (Верхня плашка)
            c.setFillColor(colors.HexColor("#2C3E50"))
            c.rect(15, height - 55, width - 30, 40, fill=1, stroke=0)

            c.setFillColor(colors.white)
            c.setFont(self.font_name, 14)
            c.drawString(30, height - 38, f"АКТ-КВИТАНЦІЯ ПРИЙОМУ В РЕМОНТ № {order_id}")
            
            c.setFont(self.font_name, 9)
            c.drawRightString(width - 30, height - 38, f"Дата прийому: {date_in}")

            # Блок 1: Інформація про Клієнта та Дати
            c.setFillColor(colors.black)
            y = height - 75

            # Лінія сітки
            c.setLineWidth(0.5)
            c.setStrokeColor(colors.HexColor("#BDC3C7"))

            c.setFont(self.font_name, 10)
            c.drawString(30, y, f"Клієнт (ПІБ): {client}")
            c.drawRightString(width - 30, y, f"Телефон: {phone}")
            
            y -= 20
            c.line(30, y + 12, width - 30, y + 12)

            # Блок 2: Інформація про обладнання
            c.setFont(self.font_name, 10)
            c.drawString(30, y, f"Обладнання / Товар: {item}")
            c.drawString(320, y, f"Серійний №: {serial}")

            y -= 20
            c.drawString(30, y, f"Комплектація: {equipment}")
            c.drawString(320, y, f"Планова дата видачі: {date_out}")

            y -= 15
            c.line(30, y + 8, width - 30, y + 8)

            # Блок 3: Несправність та статус
            y -= 10
            c.setFont(self.font_name, 10)
            c.drawString(30, y, f"Заявлена несправність: {issue}")
            
            y -= 20
            c.drawString(30, y, f"Поточний статус: {status}")

            y -= 15
            c.line(30, y + 8, width - 30, y + 8)

            # Правила та примітки
            y -= 12
            c.setFont(self.font_name, 7)
            c.setFillColor(colors.HexColor("#555555"))
            notes = (
                "1. Видача обладнання здійснюється тільки при наявності даної квитанції.\n"
                "2. Сервісний центр не несе відповідальності за можливу втрату даних на носіях інформації.\n"
                "3. Обладнання з виконаним ремонтом зберігається безоплатно протягом 30 днів."
            )
            text_obj = c.beginText(30, y)
            text_obj.setLeading(9)
            for line in notes.split('\n'):
                text_obj.textLine(line)
            c.drawText(text_obj)

            # Підписи
            y_sig = 45
            c.setFont(self.font_name, 9)
            c.setFillColor(colors.black)
            c.drawString(30, y_sig, "Замовник: ____________________ (підпис)")
            c.drawRightString(width - 30, y_sig, "Прийняв: ____________________ (підпис)")

            c.save()

            QMessageBox.information(self, "Успіх", f"Квитанцію А5 сформовано:\n{pdf_filename}")

            if sys.platform == "win32":
                os.startfile(pdf_filename)
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося створити квитанцію: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ServiceManagerApp()
    window.show()
    sys.exit(app.exec())
