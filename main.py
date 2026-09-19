import sys
import os
import sqlite3
import urllib.request
from datetime import datetime, timedelta

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QDateEdit, QComboBox, QCheckBox, QDialog
)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QPixmap, QColor

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

def get_logo_path():
    """Повертає шлях до файлу логотипу, якщо він існує."""
    base_path = os.path.dirname(os.path.abspath(__file__))
    for ext in ['logo.png', 'logo.jpg', 'logo.jpeg']:
        path = os.path.join(base_path, ext)
        if os.path.exists(path):
            return path
    return None

class TrashDialog(QDialog):
    """Вікно кошика видалених замовлень"""
    def __init__(self, conn, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.cursor = self.conn.cursor()
        self.setWindowTitle("🗑️ Кошик видалених замовлень")
        self.setGeometry(150, 150, 1000, 500)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        top_layout = QHBoxLayout()
        info_label = QLabel("Список видалених замовлень (ви можете відновити їх або видалити назавжди):")
        top_layout.addWidget(info_label)
        top_layout.addStretch()
        layout.addLayout(top_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(12)
        self.table.setHorizontalHeaderLabels([
            "ID", "Клієнт", "Телефон", "Дата продажу", "Дата прийому", "Дата видачі", 
            "Товар", "Серійний №", "Комплектація", "Несправність", "Статус", "Дата видалення"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        
        restore_btn = QPushButton("♻️ Відновити обране замовлення")
        restore_btn.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; padding: 6px;")
        restore_btn.clicked.connect(self.restore_order)

        delete_perm_btn = QPushButton("❌ Видалити назавжди")
        delete_perm_btn.setStyleSheet("background-color: #C0392B; color: white; padding: 6px;")
        delete_perm_btn.clicked.connect(self.delete_permanently)

        clear_all_btn = QPushButton("🧹 Очистити весь кошик")
        clear_all_btn.clicked.connect(self.clear_all_trash)

        btn_layout.addWidget(restore_btn)
        btn_layout.addWidget(delete_perm_btn)
        btn_layout.addWidget(clear_all_btn)
        layout.addLayout(btn_layout)

        self.load_trash()

    def load_trash(self):
        self.table.setRowCount(0)
        self.cursor.execute("SELECT original_id, client_name, phone, date_sale, date_in, date_out, item_name, serial_num, equipment, issue, status, deleted_at FROM deleted_orders")
        rows = self.cursor.fetchall()
        for row_idx, row_data in enumerate(rows):
            self.table.insertRow(row_idx)
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value if value else ""))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_idx, col_idx, item)

    def restore_order(self):
        selected_row = self.table.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "Увага", "Оберіть замовлення для відновлення!")
            return

        orig_id = self.table.item(selected_row, 0).text()
        client = self.table.item(selected_row, 1).text()
        phone = self.table.item(selected_row, 2).text()
        date_sale = self.table.item(selected_row, 3).text()
        date_in = self.table.item(selected_row, 4).text()
        date_out = self.table.item(selected_row, 5).text()
        item = self.table.item(selected_row, 6).text()
        serial = self.table.item(selected_row, 7).text()
        equipment = self.table.item(selected_row, 8).text()
        issue = self.table.item(selected_row, 9).text()
        status = self.table.item(selected_row, 10).text()

        self.cursor.execute("""
            INSERT INTO orders (id, client_name, phone, date_sale, date_in, date_out, item_name, serial_num, equipment, issue, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (orig_id, client, phone, date_sale, date_in, date_out, item, serial, equipment, issue, status))

        self.cursor.execute("DELETE FROM deleted_orders WHERE original_id = ?", (orig_id,))
        self.conn.commit()

        self.load_trash()
        if self.parent():
            self.parent().load_orders()
        QMessageBox.information(self, "Успіх", f"Замовлення №{orig_id} успішно відновлено!")

    def delete_permanently(self):
        selected_row = self.table.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "Увага", "Оберіть замовлення для остаточного видалення!")
            return

        confirm = QMessageBox.question(
            self, "Підтвердження", "Ви дійсно хочете остаточно видалити це замовлення? Цю дію неможливо скасувати!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            orig_id = self.table.item(selected_row, 0).text()
            self.cursor.execute("DELETE FROM deleted_orders WHERE original_id = ?", (orig_id,))
            self.conn.commit()
            self.load_trash()

    def clear_all_trash(self):
        confirm = QMessageBox.question(
            self, "Підтвердження", "Очистити весь кошик? Всі видалені замовлення будуть безповоротно втрачені!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.cursor.execute("DELETE FROM deleted_orders")
            self.conn.commit()
            self.load_trash()

class ServiceManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Облік ремонту інструменту та обладнання — БЕНЗО ІНСТРУМЕНТ")
        self.setGeometry(100, 100, 1180, 750)
        
        self.font_name = setup_cyrillic_font()
        self.logo_path = get_logo_path()
        self.is_loading = False
        
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
                status TEXT,
                date_sale TEXT
            )
        """)

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS deleted_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_id INTEGER,
                client_name TEXT,
                phone TEXT,
                date_in TEXT,
                date_out TEXT,
                item_name TEXT,
                serial_num TEXT,
                equipment TEXT,
                issue TEXT,
                status TEXT,
                date_sale TEXT,
                deleted_at TEXT
            )
        """)
        
        self.cursor.execute("PRAGMA table_info(orders)")
        columns = [column[1] for column in self.cursor.fetchall()]
        if 'date_sale' not in columns:
            self.cursor.execute("ALTER TABLE orders ADD COLUMN date_sale TEXT")

        self.conn.commit()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Верхня панель з логотипом та кнопкою Кошика
        header_layout = QHBoxLayout()
        if self.logo_path:
            logo_label = QLabel()
            pixmap = QPixmap(self.logo_path)
            logo_label.setPixmap(pixmap.scaledToHeight(45, Qt.TransformationMode.SmoothTransformation))
            header_layout.addWidget(logo_label)

        title_label = QLabel("БЕНЗО ІНСТРУМЕНТ — Сервісний Центр")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #2C3E50;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()

        trash_btn = QPushButton("🗑️ Кошик")
        trash_btn.setStyleSheet("font-size: 13px; padding: 5px 12px; background-color: #7F8C8D; color: white; font-weight: bold;")
        trash_btn.clicked.connect(self.open_trash)
        header_layout.addWidget(trash_btn)

        main_layout.addLayout(header_layout)

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
        self.has_sale_date_checkbox = QCheckBox("Вказати дату продажу:")
        self.has_sale_date_checkbox.toggled.connect(self.toggle_sale_date)
        
        self.date_sale_edit = QDateEdit()
        self.date_sale_edit.setDate(QDate.currentDate())
        self.date_sale_edit.setCalendarPopup(True)
        self.date_sale_edit.setEnabled(False)

        self.date_in_edit = QDateEdit()
        self.date_in_edit.setDate(QDate.currentDate())
        self.date_in_edit.setCalendarPopup(True)

        self.date_out_edit = QDateEdit()
        self.date_out_edit.setDate(QDate.currentDate().addMonths(3))
        self.date_out_edit.setCalendarPopup(True)

        self.status_box = QComboBox()
        self.status_box.addItems(["В роботі", "Очікує запчастин", "Готово", "Видано"])

        r3.addWidget(self.has_sale_date_checkbox)
        r3.addWidget(self.date_sale_edit)
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
        
        quick_order_btn = QPushButton("⚡ Швидке замовлення")
        quick_order_btn.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; padding: 6px;")
        quick_order_btn.clicked.connect(self.quick_order)

        save_btn = QPushButton("Зберегти замовлення з форми")
        save_btn.clicked.connect(self.save_order)
        
        print_btn = QPushButton("Роздрукувати квитанцію (А5)")
        print_btn.clicked.connect(self.print_receipt)

        delete_btn = QPushButton("Видалити замовлення в кошик")
        delete_btn.setStyleSheet("background-color: #E74C3C; color: white;")
        delete_btn.clicked.connect(self.delete_order)

        btn_layout.addWidget(quick_order_btn)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(print_btn)
        btn_layout.addWidget(delete_btn)
        main_layout.addLayout(btn_layout)

        # Поле пошуку з кнопкою очищення (хрестиком)
        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Пошук (ПІБ або Телефон):")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введіть ім'я або номер телефону для фільтрації...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.search_orders)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        main_layout.addLayout(search_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "ID", "Клієнт", "Телефон", "Дата продажу", "Дата прийому", "Дата видачі", 
            "Товар", "Серійний №", "Комплектація", "Несправність", "Статус"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.fill_form_from_table)
        self.table.cellChanged.connect(self.auto_save_cell)
        main_layout.addWidget(self.table)

        self.load_orders()

    def open_trash(self):
        """Відкриває діалогове вікно кошика."""
        dialog = TrashDialog(self.conn, self)
        dialog.exec()

    def toggle_sale_date(self, checked):
        self.date_sale_edit.setEnabled(checked)

    def quick_order(self):
        """Створює нове замовлення прямо в таблиці і відразу додає його в БД."""
        today = QDate.currentDate().toString("yyyy-MM-dd")
        date_out_default = QDate.currentDate().addMonths(3).toString("yyyy-MM-dd")

        self.cursor.execute("""
            INSERT INTO orders (client_name, phone, date_sale, date_in, date_out, item_name, serial_num, equipment, issue, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("", "", "", today, date_out_default, "", "", "", "", "В роботі"))
        self.conn.commit()

        self.load_orders()
        new_row_idx = self.table.rowCount() - 1
        self.table.selectRow(new_row_idx)
        self.table.editItem(self.table.item(new_row_idx, 1))

    def auto_save_cell(self, row, column):
        """Автоматично оновлює відповідне поле в БД при редагуванні комірки таблиці."""
        if self.is_loading:
            return

        order_id_item = self.table.item(row, 0)
        if not order_id_item or not order_id_item.text():
            return

        order_id = order_id_item.text()
        new_value = self.table.item(row, column).text().strip()

        col_db_map = {
            1: "client_name",
            2: "phone",
            3: "date_sale",
            4: "date_in",
            5: "date_out",
            6: "item_name",
            7: "serial_num",
            8: "equipment",
            9: "issue",
            10: "status"
        }

        if column in col_db_map:
            field_name = col_db_map[column]
            query = f"UPDATE orders SET {field_name} = ? WHERE id = ?"
            self.cursor.execute(query, (new_value, order_id))
            self.conn.commit()

            # Оновлюємо підсвічування рядка в разі зміни дати прийому або статусу
            if column in (4, 10):
                self.apply_row_highlight(row)

    def is_overdue(self, date_in_str, status_str):
        """Перевіряє, чи замовлення прийняте більше двох тижнів (14 днів) тому і не закрите."""
        if not date_in_str or status_str in ["Готово", "Видано"]:
            return False

        try:
            date_in = datetime.strptime(date_in_str, "%Y-%m-%d").date()
            today = datetime.now().date()
            return (today - date_in).days > 14
        except ValueError:
            return False

    def apply_row_highlight(self, row_idx):
        """Підсвічує рядок світло-червоним кольором, якщо замовлення протерміноване (>14 днів)."""
        date_in_item = self.table.item(row_idx, 4)
        status_item = self.table.item(row_idx, 10)

        date_in_str = date_in_item.text() if date_in_item else ""
        status_str = status_item.text() if status_item else ""

        highlight_color = QColor("#FFCDD2") if self.is_overdue(date_in_str, status_str) else QColor("#FFFFFF")

        for col_idx in range(self.table.columnCount()):
            item = self.table.item(row_idx, col_idx)
            if item:
                item.setBackground(highlight_color)

    def save_order(self):
        client = self.client_input.text().strip()
        phone = self.phone_input.text().strip()
        
        if self.has_sale_date_checkbox.isChecked():
            date_sale = self.date_sale_edit.date().toString("yyyy-MM-dd")
        else:
            date_sale = ""

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
            INSERT INTO orders (client_name, phone, date_in, date_out, item_name, serial_num, equipment, issue, status, date_sale)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (client, phone, date_in, date_out, item, serial, equipment, issue, status, date_sale))
        self.conn.commit()

        self.clear_fields()
        self.load_orders()
        QMessageBox.information(self, "Успіх", "Замовлення збережено!")

    def load_orders(self):
        self.is_loading = True
        self.table.setRowCount(0)
        self.cursor.execute("SELECT id, client_name, phone, date_sale, date_in, date_out, item_name, serial_num, equipment, issue, status FROM orders")
        rows = self.cursor.fetchall()
        for row_idx, row_data in enumerate(rows):
            self.table.insertRow(row_idx)
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value if value else ""))
                if col_idx == 0:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_idx, col_idx, item)
            
            # Застосовуємо підсвічування для кожного рядка
            self.apply_row_highlight(row_idx)

        self.is_loading = False

    def search_orders(self):
        self.is_loading = True
        query = self.search_input.text().strip()
        self.table.setRowCount(0)
        
        if not query:
            self.cursor.execute("SELECT id, client_name, phone, date_sale, date_in, date_out, item_name, serial_num, equipment, issue, status FROM orders")
        else:
            search_pattern = f"%{query}%"
            self.cursor.execute("""
                SELECT id, client_name, phone, date_sale, date_in, date_out, item_name, serial_num, equipment, issue, status FROM orders 
                WHERE client_name LIKE ? OR phone LIKE ?
            """, (search_pattern, search_pattern))
            
        rows = self.cursor.fetchall()
        for row_idx, row_data in enumerate(rows):
            self.table.insertRow(row_idx)
            for col_idx, value in enumerate(row_data):
                item = QTableWidgetItem(str(value if value else ""))
                if col_idx == 0:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_idx, col_idx, item)

            self.apply_row_highlight(row_idx)

        self.is_loading = False

    def fill_form_from_table(self):
        selected_row = self.table.currentRow()
        if selected_row >= 0:
            client_item = self.table.item(selected_row, 1)
            phone_item = self.table.item(selected_row, 2)
            item_item = self.table.item(selected_row, 6)
            
            if client_item: self.client_input.setText(client_item.text())
            if phone_item: self.phone_input.setText(phone_item.text())
            
            date_sale_item = self.table.item(selected_row, 3)
            date_sale_str = date_sale_item.text() if date_sale_item else ""
            if date_sale_str and date_sale_str != "None":
                self.has_sale_date_checkbox.setChecked(True)
                self.date_sale_edit.setDate(QDate.fromString(date_sale_str, "yyyy-MM-dd"))
            else:
                self.has_sale_date_checkbox.setChecked(False)

            date_in_item = self.table.item(selected_row, 4)
            date_in_str = date_in_item.text() if date_in_item else ""
            if date_in_str:
                self.date_in_edit.setDate(QDate.fromString(date_in_str, "yyyy-MM-dd"))
            
            date_out_item = self.table.item(selected_row, 5)
            date_out_str = date_out_item.text() if date_out_item else ""
            if date_out_str:
                self.date_out_edit.setDate(QDate.fromString(date_out_str, "yyyy-MM-dd"))

            if item_item: self.item_input.setText(item_item.text())
            
            serial_item = self.table.item(selected_row, 7)
            if serial_item: self.serial_input.setText(serial_item.text())
            
            equipment_item = self.table.item(selected_row, 8)
            if equipment_item: self.equipment_input.setText(equipment_item.text())
            
            issue_item = self.table.item(selected_row, 9)
            if issue_item: self.issue_input.setText(issue_item.text())

    def clear_fields(self):
        self.client_input.clear()
        self.phone_input.clear()
        self.item_input.clear()
        self.serial_input.clear()
        self.equipment_input.clear()
        self.issue_input.clear()
        self.search_input.clear()
        self.has_sale_date_checkbox.setChecked(False)
        self.date_sale_edit.setDate(QDate.currentDate())
        self.date_in_edit.setDate(QDate.currentDate())
        self.date_out_edit.setDate(QDate.currentDate().addMonths(3))

    def delete_order(self):
        """Переміщує вибране замовлення з таблиці orders у deleted_orders."""
        selected_row = self.table.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "Помилка", "Оберіть рядок!")
            return

        order_id = self.table.item(selected_row, 0).text()

        self.cursor.execute("SELECT id, client_name, phone, date_in, date_out, item_name, serial_num, equipment, issue, status, date_sale FROM orders WHERE id = ?", (order_id,))
        row = self.cursor.fetchone()

        if row:
            deleted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.cursor.execute("""
                INSERT INTO deleted_orders (original_id, client_name, phone, date_in, date_out, item_name, serial_num, equipment, issue, status, date_sale, deleted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (row[0], row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10], deleted_at))

            self.cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
            self.conn.commit()

            self.load_orders()
            self.clear_fields()
            QMessageBox.information(self, "Кошик", f"Замовлення №{order_id} переміщено в кошик.")

    def print_receipt(self):
        selected_row = self.table.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "Увага", "Будь ласка, оберіть замовлення зі списку таблиці!")
            return

        try:
            order_id = self.table.item(selected_row, 0).text()
            client = self.table.item(selected_row, 1).text()
            phone = self.table.item(selected_row, 2).text()
            date_sale = self.table.item(selected_row, 3).text()
            date_in = self.table.item(selected_row, 4).text()
            date_out = self.table.item(selected_row, 5).text()
            item = self.table.item(selected_row, 6).text()
            serial = self.table.item(selected_row, 7).text()
            equipment = self.table.item(selected_row, 8).text()
            issue = self.table.item(selected_row, 9).text()
            status = self.table.item(selected_row, 10).text()

            display_date_sale = date_sale if (date_sale and date_sale != "None") else "—"

            docs_dir = os.path.join(os.path.expanduser('~'), 'Documents')
            pdf_filename = os.path.join(docs_dir, f"Квитанция_A5_{order_id}.pdf")
            
            c = canvas.Canvas(pdf_filename, pagesize=landscape(A5))
            width, height = landscape(A5)

            # Зовнішня рамка
            c.setStrokeColor(colors.HexColor("#2C3E50"))
            c.setLineWidth(1.5)
            c.rect(15, 15, width - 30, height - 30)

            # Верхня плашка заголовка
            c.setFillColor(colors.HexColor("#2C3E50"))
            c.rect(15, height - 55, width - 30, 40, fill=1, stroke=0)

            text_x = 30
            if self.logo_path:
                try:
                    c.drawImage(self.logo_path, 20, height - 50, width=90, height=30, preserveAspectRatio=True, mask='auto')
                    text_x = 120
                except Exception:
                    pass

            c.setFillColor(colors.white)
            c.setFont(self.font_name, 13)
            c.drawString(text_x, height - 38, f"АКТ-КВИТАНЦІЯ ПРИЙОМУ В РЕМОНТ № {order_id}")
            
            c.setFont(self.font_name, 9)
            c.drawRightString(width - 30, height - 38, f"Дата прийому: {date_in}")

            # Блок 1: Інформація про Клієнта та Дати
            c.setFillColor(colors.black)
            y = height - 75

            c.setLineWidth(0.5)
            c.setStrokeColor(colors.HexColor("#BDC3C7"))

            c.setFont(self.font_name, 10)
            c.drawString(30, y, f"Клієнт (ПІБ): {client}")
            c.drawRightString(width - 30, y, f"Телефон: {phone}")
            
            y -= 20
            c.line(30, y + 12, width - 30, y + 12)

            # Блок 2: Інформація про обладнання та дати
            c.setFont(self.font_name, 10)
            c.drawString(30, y, f"Обладнання / Товар: {item}")
            c.drawString(320, y, f"Серійний №: {serial}")

            y -= 20
            c.drawString(30, y, f"Комплектація: {equipment}")
            c.drawString(320, y, f"Дата продажу: {display_date_sale}")

            y -= 20
            c.drawString(30, y, f"Поточний статус: {status}")
            c.drawString(320, y, f"Планова дата видачі: {date_out}")

            y -= 15
            c.line(30, y + 8, width - 30, y + 8)

            # Блок 3: Несправність
            y -= 10
            c.setFont(self.font_name, 10)
            c.drawString(30, y, f"Заявлена несправність: {issue}")

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
            y_sig = 40
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
