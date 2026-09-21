import sys
import os
import sqlite3
import shutil
import urllib.request
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QDateEdit, QComboBox, QCheckBox,
    QDialog, QFileDialog, QScrollArea, QStyledItemDelegate
)
from PyQt6.QtCore import QDate, Qt
from PyQt6.QtGui import QPixmap, QColor
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4

# --- ВИЗНАЧЕННЯ БАЗОВОЇ ПАПКИ ТА UPLOAD_DIR В APPDATA ---
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

APP_DATA_DIR = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'ServiceManager')
os.makedirs(APP_DATA_DIR, exist_ok=True)

UPLOAD_DIR = os.path.join(APP_DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

PYTHON_DATE_FORMAT = "%d.%m.%Y"


def format_date_to_ukr(date_str):
    """Конвертує дату у формат dd.MM.yyyy"""
    if not date_str or date_str == "None":
        return ""
    d = QDate.fromString(str(date_str), "dd.MM.yyyy")
    if d.isValid():
        return d.toString("dd.MM.yyyy")
    d = QDate.fromString(str(date_str), "yyyy-MM-dd")
    if d.isValid():
        return d.toString("dd.MM.yyyy")
    return str(date_str)


def setup_cyrillic_font():
    """Системний шрифт для кирилиці в PDF"""
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
    base_path = BASE_DIR
    for ext in ['logo.png', 'logo.jpg', 'logo.jpeg']:
        path = os.path.join(base_path, ext)
        if os.path.exists(path):
            return path
    return None


class DateDelegate(QStyledItemDelegate):
    """Делегат для вибору дати з календаря в таблиці"""
    def createEditor(self, parent, option, index):
        editor = QDateEdit(parent)
        editor.setDisplayFormat("dd.MM.yyyy")
        editor.setCalendarPopup(True)
        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, Qt.ItemDataRole.EditRole) or ""
        d = QDate.fromString(str(value), "dd.MM.yyyy")
        if not d.isValid():
            d = QDate.fromString(str(value), "yyyy-MM-dd")
        if not d.isValid():
            d = QDate.currentDate()
        editor.setDate(d)

    def setModelData(self, editor, model, index):
        date_str = editor.date().toString("dd.MM.yyyy")
        model.setData(index, date_str, Qt.ItemDataRole.EditRole)


class PhotoViewerDialog(QDialog):
    """Перегляд та видалення фотографій"""
    def __init__(self, order_id, conn, parent=None):
        super().__init__(parent)
        self.order_id = order_id
        self.conn = conn
        self.cursor = self.conn.cursor()
        self.setWindowTitle(f"🖼️ Фотографії замовлення №{self.order_id}")
        self.resize(650, 550)
        self.init_ui()

    def init_ui(self):
        self.layout = QVBoxLayout(self)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.load_photos_widget()
        self.layout.addWidget(self.scroll)

        btn_close = QPushButton("Закрити")
        btn_close.setStyleSheet("padding: 6px; font-weight: bold;")
        btn_close.clicked.connect(self.accept)
        self.layout.addWidget(btn_close)

    def load_photos_widget(self):
        content_widget = QWidget()
        scroll_layout = QVBoxLayout(content_widget)

        self.cursor.execute("SELECT id, photo_path FROM order_photos WHERE order_id = ?", (self.order_id,))
        photos = self.cursor.fetchall()

        if not photos:
            scroll_layout.addWidget(QLabel("До цього замовлення немає доданих фотографій."))
        else:
            for photo_id, path in photos:
                photo_item_layout = QVBoxLayout()
                if os.path.exists(path):
                    lbl = QLabel()
                    pixmap = QPixmap(path)
                    lbl.setPixmap(pixmap.scaledToWidth(550, Qt.TransformationMode.SmoothTransformation))
                    photo_item_layout.addWidget(lbl)
                else:
                    photo_item_layout.addWidget(QLabel(f"Файл не знайдено: {path}"))

                btn_delete_photo = QPushButton("🗑️ Видалити фото")
                btn_delete_photo.setStyleSheet(
                    "background-color: #E74C3C; color: white; font-weight: bold; padding: 4px; margin-bottom: 15px;"
                )
                btn_delete_photo.clicked.connect(lambda _, pid=photo_id, ppath=path: self.delete_photo(pid, ppath))
                photo_item_layout.addWidget(btn_delete_photo)

                scroll_layout.addLayout(photo_item_layout)

        self.scroll.setWidget(content_widget)

    def delete_photo(self, photo_id, photo_path):
        confirm = QMessageBox.question(
            self, "Підтвердження", "Ви впевнені, що хочете видалити це фото?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                self.cursor.execute("DELETE FROM order_photos WHERE id = ?", (photo_id,))
                self.conn.commit()
                if os.path.exists(photo_path):
                    os.remove(photo_path)
                self.load_photos_widget()

                if self.parent() and hasattr(self.parent(), 'update_photo_count_for_selected_row'):
                    self.parent().update_photo_count_for_selected_row()

            except Exception as e:
                QMessageBox.critical(self, "Помилка", f"Не вдалося видалити фото: {e}")


class TrashDialog(QDialog):
    """Кошик видалених замовлень"""
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
        top_layout.addWidget(QLabel("Список видалених замовлень:"))
        top_layout.addStretch()
        layout.addLayout(top_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(12)
        self.table.setHorizontalHeaderLabels([
            "ID", "Клієнт", "Телефон", "Дата продажу", "Дата прийому",
            "Дата видачі", "Товар", "Серійний №", "Комплектація", "Несправність",
            "Статус", "Дата видалення"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        restore_btn = QPushButton("♻️ Відновити замовлення")
        restore_btn.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; padding: 6px;")
        restore_btn.clicked.connect(self.restore_order)

        delete_perm_btn = QPushButton("❌ Видалити назавжди")
        delete_perm_btn.setStyleSheet("background-color: #C0392B; color: white; padding: 6px;")
        delete_perm_btn.clicked.connect(self.delete_permanently)

        clear_all_btn = QPushButton("🧹 Очистити кошик")
        clear_all_btn.clicked.connect(self.clear_all_trash)

        btn_layout.addWidget(restore_btn)
        btn_layout.addWidget(delete_perm_btn)
        btn_layout.addWidget(clear_all_btn)
        layout.addLayout(btn_layout)

        self.load_trash()

    def load_trash(self):
        self.table.setRowCount(0)
        self.cursor.execute(
            "SELECT original_id, client_name, phone, date_sale, date_in, date_out, item_name, serial_num, equipment, issue, status, deleted_at FROM deleted_orders"
        )
        rows = self.cursor.fetchall()
        for row_idx, row_data in enumerate(rows):
            self.table.insertRow(row_idx)
            for col_idx, value in enumerate(row_data):
                val_str = str(value if value is not None else "")
                if col_idx in (3, 4, 5):
                    val_str = format_date_to_ukr(val_str)
                item = QTableWidgetItem(val_str)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_idx, col_idx, item)

    def restore_order(self):
        selected_row = self.table.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "Увага", "Оберіть замовлення для відновлення!")
            return

        orig_id = self.get_cell_text(selected_row, 0)
        client = self.get_cell_text(selected_row, 1)
        phone = self.get_cell_text(selected_row, 2)
        date_sale = self.get_cell_text(selected_row, 3)
        date_in = self.get_cell_text(selected_row, 4)
        date_out = self.get_cell_text(selected_row, 5)
        item = self.get_cell_text(selected_row, 6)
        serial = self.get_cell_text(selected_row, 7)
        equipment = self.get_cell_text(selected_row, 8)
        issue = self.get_cell_text(selected_row, 9)
        status = self.get_cell_text(selected_row, 10)

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
            QMessageBox.warning(self, "Увага", "Оберіть замовлення для видалення!")
            return

        confirm = QMessageBox.question(
            self, "Підтвердження", "Остаточно видалити замовлення?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            orig_id = self.get_cell_text(selected_row, 0)
            self.cursor.execute("DELETE FROM deleted_orders WHERE original_id = ?", (orig_id,))
            self.conn.commit()
            self.load_trash()

    def clear_all_trash(self):
        confirm = QMessageBox.question(
            self, "Підтвердження", "Очистити весь кошик?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.cursor.execute("DELETE FROM deleted_orders")
            self.conn.commit()
            self.load_trash()

    def get_cell_text(self, row, col):
        item = self.table.item(row, col)
        return item.text() if item else ""


class ServiceManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Облік ремонту інструменту та обладнання — БЕНЗО ІНСТРУМЕНТ")
        self.setGeometry(100, 100, 1200, 780)

        self.font_name = setup_cyrillic_font()
        self.logo_path = get_logo_path()
        self.is_loading = False
        self.selected_photos = []

        self.init_db()
        self.init_ui()

    def init_db(self):
        db_path = os.path.join(APP_DATA_DIR, "service_orders.db")
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

        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                photo_path TEXT,
                FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
            )
        """)

        self.cursor.execute("PRAGMA table_info(orders)")
        columns = [column[1] for column in self.cursor.fetchall()]
        if 'date_sale' not in columns:
            self.cursor.execute("ALTER TABLE orders ADD COLUMN date_sale TEXT")

        self.cursor.execute("PRAGMA table_info(deleted_orders)")
        del_columns = [column[1] for column in self.cursor.fetchall()]
        if 'date_sale' not in del_columns:
            self.cursor.execute("ALTER TABLE deleted_orders ADD COLUMN date_sale TEXT")

        self.conn.commit()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

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
        self.date_sale_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_sale_edit.setDate(QDate.currentDate())
        self.date_sale_edit.setCalendarPopup(True)
        self.date_sale_edit.setEnabled(False)

        self.date_in_edit = QDateEdit()
        self.date_in_edit.setDisplayFormat("dd.MM.yyyy")
        self.date_in_edit.setDate(QDate.currentDate())
        self.date_in_edit.setCalendarPopup(True)

        self.date_out_edit = QDateEdit()
        self.date_out_edit.setDisplayFormat("dd.MM.yyyy")
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
        self.btn_select_photo = QPushButton("📷 Додати фото")
        self.btn_select_photo.clicked.connect(self.select_photos)
        self.lbl_photo_count = QLabel("Обрано: 0")

        r4.addWidget(QLabel("Несправність:"))
        r4.addWidget(self.issue_input)
        r4.addWidget(self.btn_select_photo)
        r4.addWidget(self.lbl_photo_count)
        form_layout.addLayout(r4)

        main_layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        quick_order_btn = QPushButton("⚡ Швидке замовлення")
        quick_order_btn.setStyleSheet("background-color: #27AE60; color: white; font-weight: bold; padding: 6px;")
        quick_order_btn.clicked.connect(self.quick_order)

        save_btn = QPushButton("Зберегти замовлення")
        save_btn.clicked.connect(self.save_order)

        view_photo_btn = QPushButton("🖼️ Переглянути / видалити фото")
        view_photo_btn.setStyleSheet("background-color: #2980B9; color: white; font-weight: bold;")
        view_photo_btn.clicked.connect(self.view_photos)

        print_btn = QPushButton("Роздрукувати квитанцію (А5)")
        print_btn.clicked.connect(self.print_receipt)

        delete_btn = QPushButton("Видалити в кошик")
        delete_btn.setStyleSheet("background-color: #E74C3C; color: white;")
        delete_btn.clicked.connect(self.delete_order)

        btn_layout.addWidget(quick_order_btn)
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(view_photo_btn)
        btn_layout.addWidget(print_btn)
        btn_layout.addWidget(delete_btn)
        main_layout.addLayout(btn_layout)

        search_layout = QHBoxLayout()
        search_label = QLabel("🔍 Пошук (ПІБ або Телефон):")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введіть ім'я або номер телефону...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.search_orders)
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_input)
        main_layout.addLayout(search_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(12)
        self.table.setHorizontalHeaderLabels([
            "ID", "Клієнт", "Телефон", "Дата продажу", "Дата прийому",
            "Дата видачі", "Товар", "Серійний №", "Комплектація", "Несправність",
            "Статус", "Фото"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # Выделение всей строки целиком
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        date_delegate = DateDelegate(self.table)
        self.table.setItemDelegateForColumn(3, date_delegate)
        self.table.setItemDelegateForColumn(4, date_delegate)
        self.table.setItemDelegateForColumn(5, date_delegate)

        # Отключаем стандартную синюю подсветку Qt, чтобы работали наши QColor
        self.table.setStyleSheet("""
            QTableWidget::item:selected {
                background-color: transparent;
            }
            QTableWidget::item:focus {
                background-color: transparent;
            }
        """)

        self.table.itemSelectionChanged.connect(self.on_row_selected)
        self.table.cellChanged.connect(self.auto_save_cell)
        main_layout.addWidget(self.table)

        self.load_orders()

    def on_row_selected(self):
        if self.is_loading:
            return
        self.refresh_all_highlights()
        self.fill_form_from_table()

    def refresh_all_highlights(self):
        for r in range(self.table.rowCount()):
            self.apply_row_highlight(r)

    def select_photos(self):
        selected_row = self.table.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "Увага", "Спочатку оберіть замовлення в таблиці!")
            return

        order_id_str = self.get_cell_text(selected_row, 0)
        if not order_id_str:
            QMessageBox.warning(self, "Увага", "Неможливо додавати фото до незбереженого замовлення!")
            return

        try:
            order_id = int(order_id_str)
        except ValueError:
            return

        files, _ = QFileDialog.getOpenFileNames(
            self, "Оберіть фотографії", "",
            "Зображення (*.png *.jpg *.jpeg *.bmp *.webp *.PNG *.JPG *.JPEG *.BMP *.WEBP);;Усі файли (*.*)"
        )

        if files:
            added_count = 0
            for photo_path in files:
                if os.path.exists(photo_path):
                    try:
                        ext = os.path.splitext(photo_path)[1]
                        new_filename = f"order_{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{ext}"
                        dest_path = os.path.join(UPLOAD_DIR, new_filename)
                        shutil.copy2(photo_path, dest_path)

                        self.cursor.execute("""
                            INSERT INTO order_photos (order_id, photo_path)
                            VALUES (?, ?)
                        """, (order_id, dest_path))
                        added_count += 1
                    except Exception as e:
                        print(f"Помилка при збереженні фото: {e}")

            self.conn.commit()
            self.update_photo_count_for_selected_row()

            if added_count > 0:
                QMessageBox.information(self, "Успіх", f"Успішно додано {added_count} фото до замовлення №{order_id}!")
            else:
                QMessageBox.warning(self, "Помилка", "Не вдалося додати обрані файли. Перевірте доступ до файлів.")

    def update_photo_count_for_selected_row(self):
        selected_row = self.table.currentRow()
        if selected_row == -1:
            return
        order_id_str = self.get_cell_text(selected_row, 0)
        if not order_id_str:
            return

        try:
            order_id = int(order_id_str)
            self.cursor.execute("SELECT COUNT(*) FROM order_photos WHERE order_id = ?", (order_id,))
            photo_count = self.cursor.fetchone()[0]

            self.is_loading = True
            photo_item = QTableWidgetItem(f"📷 ({photo_count})")
            photo_item.setFlags(photo_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(selected_row, 11, photo_item)
            self.is_loading = False

            self.lbl_photo_count.setText(f"Обрано: {photo_count}")
        except ValueError:
            pass

    def view_photos(self):
        selected_row = self.table.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "Увага", "Оберіть замовлення з таблиці!")
            return
        order_id = self.get_cell_text(selected_row, 0)
        if not order_id:
            return
        dialog = PhotoViewerDialog(int(order_id), self.conn, self)
        dialog.exec()

    def open_trash(self):
        dialog = TrashDialog(self.conn, self)
        dialog.exec()

    def toggle_sale_date(self, checked):
        self.date_sale_edit.setEnabled(checked)

    def quick_order(self):
        self.clear_fields()
        today = QDate.currentDate().toString("dd.MM.yyyy")
        date_out_default = QDate.currentDate().addMonths(3).toString("dd.MM.yyyy")

        self.cursor.execute("""
            INSERT INTO orders (client_name, phone, date_sale, date_in, date_out, item_name, serial_num, equipment, issue, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("", "", "", today, date_out_default, "", "", "", "", "В роботі"))
        self.conn.commit()

        self.load_orders()
        if self.table.rowCount() > 0:
            self.table.selectRow(0)

    def auto_save_cell(self, row, column):
        if self.is_loading:
            return

        order_id = self.get_cell_text(row, 0)
        if not order_id:
            return

        new_value = self.get_cell_text(row, column)

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

            if column in (4, 10):
                self.apply_row_highlight(row)

    def is_overdue(self, date_in_str, status_str):
        if not date_in_str or status_str in ["Готово", "Видано"]:
            return False
        try:
            date_in = datetime.strptime(date_in_str, PYTHON_DATE_FORMAT).date()
            today = datetime.now().date()
            return (today - date_in).days > 14
        except ValueError:
            return False

    def apply_row_highlight(self, row_idx):
        is_selected = (self.table.currentRow() == row_idx)
        date_in_str = self.get_cell_text(row_idx, 4)
        status_str = self.get_cell_text(row_idx, 10)

        # Подсветка строки
        if is_selected:
            # Выделенная строка (светло-зеленый)
            bg_color = QColor("#D4EDDA")
            text_color = QColor("#155724")
        elif self.is_overdue(date_in_str, status_str):
            # Просроченная строка (светло-красный)
            bg_color = QColor("#F8D7DA")
            text_color = QColor("#721C24")
        else:
            # Обычная строка
            bg_color = QColor("#FFFFFF")
            text_color = QColor("#000000")

        # Применяем фоновый цвет и цвет текста ко всем ячейкам в строке
        for col_idx in range(self.table.columnCount()):
            item = self.table.item(row_idx, col_idx)
            if not item:
                item = QTableWidgetItem()
                self.table.setItem(row_idx, col_idx, item)

            item.setBackground(bg_color)
            item.setForeground(text_color)

    def save_order(self):
        client = self.client_input.text().strip()
        phone = self.phone_input.text().strip()
        date_sale = self.date_sale_edit.date().toString("dd.MM.yyyy") if self.has_sale_date_checkbox.isChecked() else ""
        date_in = self.date_in_edit.date().toString("dd.MM.yyyy")
        date_out = self.date_out_edit.date().toString("dd.MM.yyyy")
        item = self.item_input.text().strip()
        serial = self.serial_input.text().strip()
        equipment = self.equipment_input.text().strip()
        issue = self.issue_input.text().strip()
        status = self.status_box.currentText()

        selected_row = self.table.currentRow()
        order_id = self.get_cell_text(selected_row, 0) if selected_row != -1 else None

        if order_id:
            self.cursor.execute("""
                UPDATE orders
                SET client_name = ?, phone = ?, date_sale = ?, date_in = ?, date_out = ?, item_name = ?, serial_num = ?, equipment = ?, issue = ?, status = ?
                WHERE id = ?
            """, (client, phone, date_sale, date_in, date_out, item, serial, equipment, issue, status, order_id))
        else:
            self.cursor.execute("""
                INSERT INTO orders (client_name, phone, date_sale, date_in, date_out, item_name, serial_num, equipment, issue, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (client, phone, date_sale, date_in, date_out, item, serial, equipment, issue, status))

        self.conn.commit()
        self.load_orders()
        self.clear_fields()
        QMessageBox.information(self, "Успіх", "Замовлення збережено!")

    def load_orders(self):
        self.is_loading = True
        self.table.setRowCount(0)

        self.cursor.execute("""
            SELECT id, client_name, phone, date_sale, date_in, date_out, item_name, serial_num, equipment, issue, status
            FROM orders
            ORDER BY id DESC
        """)
        rows = self.cursor.fetchall()

        for row_idx, row_data in enumerate(rows):
            self.table.insertRow(row_idx)

            for col_idx in range(11):
                val = row_data[col_idx]
                val_str = str(val if val is not None else "")

                if col_idx in (3, 4, 5):
                    val_str = format_date_to_ukr(val_str)

                item = QTableWidgetItem(val_str)
                if col_idx == 0:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.table.setItem(row_idx, col_idx, item)

            order_id = row_data[0]
            self.cursor.execute("SELECT COUNT(*) FROM order_photos WHERE order_id = ?", (order_id,))
            photo_count = self.cursor.fetchone()[0]

            photo_item = QTableWidgetItem(f"📷 ({photo_count})")
            photo_item.setFlags(photo_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, 11, photo_item)

        self.is_loading = False
        self.refresh_all_highlights()

    def search_orders(self):
        query_text = self.search_input.text().strip()
        self.is_loading = True
        self.table.setRowCount(0)

        search_query = "%" + query_text + "%"
        self.cursor.execute("""
            SELECT id, client_name, phone, date_sale, date_in, date_out, item_name, serial_num, equipment, issue, status
            FROM orders
            WHERE client_name LIKE ? OR phone LIKE ?
            ORDER BY id DESC
        """, (search_query, search_query))

        rows = self.cursor.fetchall()

        for row_idx, row_data in enumerate(rows):
            self.table.insertRow(row_idx)

            for col_idx in range(11):
                val = row_data[col_idx]
                val_str = str(val if val is not None else "")

                if col_idx in (3, 4, 5):
                    val_str = format_date_to_ukr(val_str)

                item = QTableWidgetItem(val_str)
                if col_idx == 0:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                self.table.setItem(row_idx, col_idx, item)

            order_id = row_data[0]
            self.cursor.execute("SELECT COUNT(*) FROM order_photos WHERE order_id = ?", (order_id,))
            photo_count = self.cursor.fetchone()[0]

            photo_item = QTableWidgetItem(f"📷 ({photo_count})")
            photo_item.setFlags(photo_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row_idx, 11, photo_item)

        self.is_loading = False
        self.refresh_all_highlights()

    def delete_order(self):
        selected_row = self.table.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "Увага", "Оберіть замовлення для видалення!")
            return

        order_id = self.get_cell_text(selected_row, 0)
        if not order_id:
            return

        confirm = QMessageBox.question(
            self, "Підтвердження", f"Перемістити замовлення №{order_id} в кошик?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if confirm == QMessageBox.StandardButton.Yes:
            client = self.get_cell_text(selected_row, 1)
            phone = self.get_cell_text(selected_row, 2)
            date_sale = self.get_cell_text(selected_row, 3)
            date_in = self.get_cell_text(selected_row, 4)
            date_out = self.get_cell_text(selected_row, 5)
            item = self.get_cell_text(selected_row, 6)
            serial = self.get_cell_text(selected_row, 7)
            equipment = self.get_cell_text(selected_row, 8)
            issue = self.get_cell_text(selected_row, 9)
            status = self.get_cell_text(selected_row, 10)
            deleted_at = datetime.now().strftime("%d.%m.%Y %H:%M")

            self.cursor.execute("""
                INSERT INTO deleted_orders (original_id, client_name, phone, date_sale, date_in, date_out, item_name, serial_num, equipment, issue, status, deleted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (order_id, client, phone, date_sale, date_in, date_out, item, serial, equipment, issue, status, deleted_at))

            self.cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
            self.conn.commit()

            self.load_orders()
            self.clear_fields()
            QMessageBox.information(self, "Успіх", "Замовлення переміщено в кошик!")

    def fill_form_from_table(self):
        selected_row = self.table.currentRow()
        if selected_row == -1:
            return

        self.client_input.setText(self.get_cell_text(selected_row, 1))
        self.phone_input.setText(self.get_cell_text(selected_row, 2))

        date_sale_str = self.get_cell_text(selected_row, 3)
        if date_sale_str:
            self.has_sale_date_checkbox.setChecked(True)
            d = QDate.fromString(date_sale_str, "dd.MM.yyyy")
            if d.isValid():
                self.date_sale_edit.setDate(d)
        else:
            self.has_sale_date_checkbox.setChecked(False)

        d_in = QDate.fromString(self.get_cell_text(selected_row, 4), "dd.MM.yyyy")
        if d_in.isValid():
            self.date_in_edit.setDate(d_in)

        d_out = QDate.fromString(self.get_cell_text(selected_row, 5), "dd.MM.yyyy")
        if d_out.isValid():
            self.date_out_edit.setDate(d_out)

        self.item_input.setText(self.get_cell_text(selected_row, 6))
        self.serial_input.setText(self.get_cell_text(selected_row, 7))
        self.equipment_input.setText(self.get_cell_text(selected_row, 8))
        self.issue_input.setText(self.get_cell_text(selected_row, 9))

        status_text = self.get_cell_text(selected_row, 10)
        idx = self.status_box.findText(status_text)
        if idx != -1:
            self.status_box.setCurrentIndex(idx)

        self.update_photo_count_for_selected_row()

    def clear_fields(self):
        self.client_input.clear()
        self.phone_input.clear()
        self.has_sale_date_checkbox.setChecked(False)
        self.date_sale_edit.setDate(QDate.currentDate())
        self.date_in_edit.setDate(QDate.currentDate())
        self.date_out_edit.setDate(QDate.currentDate().addMonths(3))
        self.item_input.clear()
        self.serial_input.clear()
        self.equipment_input.clear()
        self.issue_input.clear()
        self.status_box.setCurrentIndex(0)
        self.lbl_photo_count.setText("Обрано: 0")

    def get_cell_text(self, row, col):
        item = self.table.item(row, col)
        return item.text() if item else ""

    def print_receipt(self):
        selected_row = self.table.currentRow()
        if selected_row == -1:
            QMessageBox.warning(self, "Увага", "Оберіть замовлення з таблиці!")
            return

        order_id = self.get_cell_text(selected_row, 0)
        if not order_id:
            return

        client = self.get_cell_text(selected_row, 1)
        phone = self.get_cell_text(selected_row, 2)
        date_sale = self.get_cell_text(selected_row, 3)
        date_in = self.get_cell_text(selected_row, 4)
        date_out = self.get_cell_text(selected_row, 5)
        item = self.get_cell_text(selected_row, 6)
        serial = self.get_cell_text(selected_row, 7)
        equipment = self.get_cell_text(selected_row, 8)
        issue = self.get_cell_text(selected_row, 9)

        file_path, _ = QFileDialog.getSaveFileName(self, "Зберегти квитанцію", f"Квитанція_{order_id}.pdf", "PDF файли (*.pdf)")
        if not file_path:
            return

        try:
            c = canvas.Canvas(file_path, pagesize=A4)
            width, height = A4

            def draw_receipt_copy(y_offset, title_suffix):
                c.setFont(self.font_name, 12)

                if self.logo_path:
                    try:
                        c.drawImage(self.logo_path, 40, y_offset + 340, width=110, height=40, preserveAspectRatio=True)
                    except Exception:
                        pass

                c.drawString(160, y_offset + 365, "СЕРВІСНИЙ ЦЕНТР «БЕНЗО ІНСТРУМЕНТ»")
                c.setFont(self.font_name, 9)
                c.drawString(160, y_offset + 350, "м. Вінниця, вул. Лебединського 15 | Тел: (098) 551-73-21, (093) 104-20-40")

                c.setFont(self.font_name, 11)
                c.drawString(40, y_offset + 320, f"КВИТАНЦІЯ ПРО ПРИЙОМ НА РЕМОНТ № {order_id} {title_suffix}")
                c.setLineWidth(1)
                c.line(40, y_offset + 312, width - 40, y_offset + 312)

                c.setFont(self.font_name, 10)
                curr_y = y_offset + 292
                line_height = 16

                c.drawString(40, curr_y, f"Клієнт: {client}")
                c.drawString(320, curr_y, f"Телефон: {phone}")
                curr_y -= line_height

                if date_sale:
                    c.drawString(40, curr_y, f"Дата продажу: {date_sale}")
                    curr_y -= line_height

                c.drawString(40, curr_y, f"Дата прийому: {date_in}")
                c.drawString(320, curr_y, f"Орієнтовна дата видачі: {date_out}")
                curr_y -= line_height

                c.drawString(40, curr_y, f"Найменування товару: {item}")
                curr_y -= line_height

                c.drawString(40, curr_y, f"Серійний номер: {serial}")
                curr_y -= line_height

                c.drawString(40, curr_y, f"Комплектація: {equipment}")
                curr_y -= line_height

                c.drawString(40, curr_y, f"Опис несправності: {issue}")
                curr_y -= (line_height + 5)

                c.setFont(self.font_name, 7)
                rules = [
                    "УМОВИ ОБСЛУГОВУВАННЯ ТА ГАРАНТІЇ:",
                    "1. Сервісний центр не несе відповідальності за приховані дефекти, не вказані при прийомі.",
                    "2. Видача інструменту здійснюється тільки при наявності даної квитанції.",
                    "3. Зауваження щодо стану та комплектації приймаються безпосередньо при отриманні товару."
                ]
                for r in rules:
                    c.drawString(40, curr_y, r)
                    curr_y -= 9

                curr_y -= 10
                c.setFont(self.font_name, 9)
                c.drawString(40, curr_y, "Замовник: ____________________")
                c.drawString(320, curr_y, "Прийняв: ____________________")

            draw_receipt_copy(410, "(Примірник Клієнта)")

            c.setDash(2, 2)
            c.line(40, 400, width - 40, 400)
            c.setDash()

            draw_receipt_copy(0, "(Примірник Сервісу)")

            c.save()
            QMessageBox.information(self, "Успіх", f"Квитанцію успішно збережено в PDF:\n{file_path}")

        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося згенерувати PDF: {e}")


def main():
    app = QApplication(sys.argv)
    window = ServiceManagerApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
