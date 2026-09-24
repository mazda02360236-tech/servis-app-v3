import sys
import os
import sqlite3
from datetime import datetime, date

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLineEdit, QTextEdit, QComboBox, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QDialog, QLabel, QFileDialog, QListWidget, QListWidgetItem,
    QSplitter, QAbstractItemView, QDateEdit, QToolButton
)
from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QColor, QFont, QIcon, QPixmap

# --- Підключення ReportLab для формування PDF ---
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# Налаштування кириличних шрифтів для PDF
def setup_pdf_fonts():
    font_name = "Helvetica"
    try:
        arial_path = "C:\\Windows\\Fonts\\arial.ttf"
        if os.path.exists(arial_path):
            pdfmetrics.registerFont(TTFont("CustomArial", arial_path))
            font_name = "CustomArial"
    except Exception as e:
        print(f"Помилка завантаження шрифту Arial: {e}")
    return font_name


# --- Кастомне поле пошуку з кнопкою очищення ---
class CustomSearchLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("Швидкий пошук (ПІБ, телефон, модель, №)...")
        self.clear_button = QToolButton(self)
        self.clear_button.setText("✕")
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.setStyleSheet("""
            QToolButton { border: none; background: transparent; color: #888; font-weight: bold; }
            QToolButton:hover { color: #333; }
        """)
        self.clear_button.clicked.connect(self.clear)
        self.textChanged.connect(self.update_clear_button)
        self.update_clear_button(self.text())

    def resizeEvent(self, event):
        sz = self.clear_button.sizeHint()
        frame_width = self.style().pixelMetric(self.style().PixelMetric.PM_DefaultFrameWidth)
        self.clear_button.move(self.rect().right() - frame_width - sz.width(),
                               (self.rect().bottom() + 1 - sz.height()) // 2)
        super().resizeEvent(event)

    def update_clear_button(self, text):
        self.clear_button.setVisible(bool(text))


# --- Вікно перегляду фотографій ---
class PhotoViewerDialog(QDialog):
    def __init__(self, photo_path, photo_id, db_conn, parent=None):
        super().__init__(parent)
        self.photo_path = photo_path
        self.photo_id = photo_id
        self.conn = db_conn
        self.setWindowTitle("Перегляд фотографії")
        self.resize(700, 550)

        layout = QVBoxLayout(self)
        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        pixmap = QPixmap(photo_path)
        if not pixmap.isNull():
            self.img_label.setPixmap(pixmap.scaled(680, 480, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.img_label.setText("Помилка завантаження фотографії")

        layout.addWidget(self.img_label)

        btn_layout = QHBoxLayout()
        btn_delete = QPushButton("Видалити фото")
        btn_delete.setStyleSheet("background-color: #f44336; color: white; padding: 6px;")
        btn_delete.clicked.connect(self.delete_photo)
        
        btn_close = QPushButton("Закрити")
        btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(btn_delete)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        layout.addLayout(btn_layout)

    def delete_photo(self):
        reply = QMessageBox.question(self, "Підтвердження", "Видалити це фото?", 
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM order_photos WHERE id = ?", (self.photo_id,))
            self.conn.commit()
            if os.path.exists(self.photo_path):
                try:
                    os.remove(self.photo_path)
                except Exception:
                    pass
            self.accept()


# --- Вікно деталей замовлення ---
class OrderDetailsDialog(QDialog):
    def __init__(self, order_id, db_conn, parent=None):
        super().__init__(parent)
        self.order_id = order_id
        self.conn = db_conn
        self.setWindowTitle(f"Картка замовлення №{order_id}")
        self.resize(650, 500)

        self.init_ui()
        self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.info_label = QLabel()
        self.info_label.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(self.info_label)

        layout.addWidget(QLabel("<b>Прикріплені фотографії:</b>"))
        self.photo_list = QListWidget()
        self.photo_list.setIconSize(Qt.Size(100, 100))
        self.photo_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.photo_list.itemDoubleClicked.connect(self.open_photo)
        layout.addWidget(self.photo_list)

        btn_add_photo = QPushButton("Додати фото")
        btn_add_photo.clicked.connect(self.add_photo)
        layout.addWidget(btn_add_photo)

        btn_close = QPushButton("Закрити")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def load_data(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM service_orders WHERE id = ?", (self.order_id,))
        order = cursor.fetchone()

        if order:
            info_html = f"""
            <h3>Замовлення №{order[0]}</h3>
            <p><b>Клієнт:</b> {order[1]} | <b>Телефон:</b> {order[2]}</p>
            <p><b>Модель:</b> {order[3]} | <b>Заводський №:</b> {order[4]}</p>
            <p><b>Статус:</b> {order[5]} | <b>Дата прийому:</b> {order[6]} | <b>Дата продажу:</b> {order[7] or '—'}</p>
            <p><b>Опис несправності:</b> {order[8]}</p>
            <p><b>Вартість:</b> {order[9]} грн | <b>Примітки:</b> {order[10]}</p>
            """
            self.info_label.setText(info_html)

        self.load_photos()

    def load_photos(self):
        self.photo_list.clear()
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, photo_path FROM order_photos WHERE order_id = ?", (self.order_id,))
        photos = cursor.fetchall()

        for p_id, p_path in photos:
            if os.path.exists(p_path):
                item = QListWidgetItem()
                item.setIcon(QIcon(p_path))
                item.setData(Qt.ItemDataRole.UserRole, (p_id, p_path))
                self.photo_list.addItem(item)

    def open_photo(self, item):
        p_id, p_path = item.data(Qt.ItemDataRole.UserRole)
        dlg = PhotoViewerDialog(p_path, p_id, self.conn, self)
        dlg.exec()
        self.load_photos()

    def add_photo(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Оберіть фотографії", "", "Зображення (*.png *.jpg *.jpeg)")
        if files:
            app_dir = os.path.dirname(os.path.abspath(__file__))
            photos_dir = os.path.join(app_dir, "photos")
            os.makedirs(photos_dir, exist_ok=True)

            cursor = self.conn.cursor()
            for file_path in files:
                ext = os.path.splitext(file_path)[1]
                new_filename = f"order_{self.order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{ext}"
                dest_path = os.path.join(photos_dir, new_filename)
                
                with open(file_path, 'rb') as src, open(dest_path, 'wb') as dst:
                    dst.write(src.read())

                cursor.execute("INSERT INTO order_photos (order_id, photo_path) VALUES (?, ?)", (self.order_id, dest_path))
            self.conn.commit()
            self.load_photos()


# --- Вікно кошика (видалені замовлення) ---
class TrashDialog(QDialog):
    def __init__(self, db_conn, parent=None):
        super().__init__(parent)
        self.conn = db_conn
        self.setWindowTitle("Кошик видалених замовлень")
        self.resize(700, 400)

        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["ID", "Клієнт", "Телефон", "Модель", "Дата видалення", "Причина"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        btn_restore = QPushButton("Відновити обране")
        btn_restore.clicked.connect(self.restore_order)
        btn_clear = QPushButton("Очистити кошик")
        btn_clear.setStyleSheet("background-color: #f44336; color: white;")
        btn_clear.clicked.connect(self.clear_trash)

        btn_layout.addWidget(btn_restore)
        btn_layout.addWidget(btn_clear)
        layout.addLayout(btn_layout)

        self.load_trash()

    def load_trash(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, client_name, phone, tool_model, date_deleted, reason FROM deleted_orders")
        rows = cursor.fetchall()
        self.table.setRowCount(0)

        for row_idx, row_data in enumerate(rows):
            self.table.insertRow(row_idx)
            for col_idx, value in enumerate(row_data):
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(str(value)))

    def restore_order(self):
        selected = self.table.currentRow()
        if selected < 0:
            QMessageBox.warning(self, "Увага", "Оберіть замовлення для відновлення!")
            return

        order_id = int(self.table.item(selected, 0).text())
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM deleted_orders WHERE id = ?", (order_id,))
        deleted_data = cursor.fetchone()

        if deleted_data:
            # Повертаємо в основну таблицю
            cursor.execute("""
                INSERT INTO service_orders (id, client_name, phone, tool_model, serial_num, status, date_accepted, date_sale, issue_description, cost, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, deleted_data[:11])
            
            cursor.execute("DELETE FROM deleted_orders WHERE id = ?", (order_id,))
            self.conn.commit()
            QMessageBox.information(self, "Успіх", f"Замовлення №{order_id} відновлено!")
            self.load_trash()
            if self.parent():
                self.parent().load_orders()

    def clear_trash(self):
        reply = QMessageBox.question(self, "Очищення", "Остаточно видалити всі записи з кошика?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM deleted_orders")
            self.conn.commit()
            self.load_trash()


# --- Головне вікно програми ---
class ServiceManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("БЕНЗО ІНСТРУМЕНТ - Сервісний Центр")
        self.resize(1200, 700)
        self.setAcceptDrops(True)
        self.is_loading = False

        self.init_db()
        self.init_ui()
        self.load_orders()

    def init_db(self):
        app_data = os.path.join(os.getenv('APPDATA', os.path.expanduser('~')), 'ServiceManager')
        os.makedirs(app_data, exist_ok=True)
        db_path = os.path.join(app_data, 'service_orders.db')

        self.conn = sqlite3.connect(db_path)
        cursor = self.conn.cursor()

        # Таблиця замовлень
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_name TEXT,
                phone TEXT,
                tool_model TEXT,
                serial_num TEXT,
                status TEXT,
                date_accepted TEXT,
                date_sale TEXT,
                issue_description TEXT,
                cost REAL,
                notes TEXT
            )
        """)

        # Міграція: додавання date_sale, якщо відсутня
        cursor.execute("PRAGMA table_info(service_orders)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'date_sale' not in columns:
            cursor.execute("ALTER TABLE service_orders ADD COLUMN date_sale TEXT")

        # Таблиця видалених
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS deleted_orders (
                id INTEGER PRIMARY KEY,
                client_name TEXT,
                phone TEXT,
                tool_model TEXT,
                serial_num TEXT,
                status TEXT,
                date_accepted TEXT,
                date_sale TEXT,
                issue_description TEXT,
                cost REAL,
                notes TEXT,
                date_deleted TEXT,
                reason TEXT
            )
        """)

        # Таблиця фотографій
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_photos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                photo_path TEXT,
                FOREIGN KEY(order_id) REFERENCES service_orders(id)
            )
        """)
        self.conn.commit()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Ліва панель (Форма створення/редагування) ---
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)

        title_label = QLabel("<b>Нове замовлення</b>")
        title_label.setFont(QFont("Arial", 12))
        form_layout.addWidget(title_label)

        f_layout = QFormLayout()
        self.input_client = QLineEdit()
        self.input_phone = QLineEdit()
        self.input_model = QLineEdit()
        self.input_serial = QLineEdit()

        self.combo_status = QComboBox()
        self.combo_status.addItems(["В роботі", "Очікує запчастини", "Готово", "Видано"])

        self.input_date_accepted = QDateEdit()
        self.input_date_accepted.setCalendarPopup(True)
        self.input_date_accepted.setDate(QDate.currentDate())

        self.input_date_sale = QDateEdit()
        self.input_date_sale.setCalendarPopup(True)
        self.input_date_sale.setSpecialValueText("—")
        self.input_date_sale.setDate(QDate(2000, 1, 1))

        self.input_issue = QTextEdit()
        self.input_issue.setMaximumHeight(60)

        self.input_cost = QLineEdit()
        self.input_cost.setPlaceholderText("0.00")

        self.input_notes = QTextEdit()
        self.input_notes.setMaximumHeight(60)

        f_layout.addRow("ПІБ Клієнта:", self.input_client)
        f_layout.addRow("Телефон:", self.input_phone)
        f_layout.addRow("Модель:", self.input_model)
        f_layout.addRow("Заводський №:", self.input_serial)
        f_layout.addRow("Статус:", self.combo_status)
        f_layout.addRow("Дата прийому:", self.input_date_accepted)
        f_layout.addRow("Дата продажу:", self.input_date_sale)
        f_layout.addRow("Несправність:", self.input_issue)
        f_layout.addRow("Вартість (грн):", self.input_cost)
        f_layout.addRow("Примітки:", self.input_notes)

        form_layout.addLayout(f_layout)

        btn_add = QPushButton("Прийняти в ремонт")
        btn_add.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold; padding: 8px;")
        btn_add.clicked.connect(self.add_order)
        form_layout.addWidget(btn_add)

        btn_trash = QPushButton("Кошик видалених")
        btn_trash.clicked.connect(self.open_trash)
        form_layout.addWidget(btn_trash)

        form_layout.addStretch()

        # --- Права панель (Таблиця + Пошук) ---
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)

        top_bar = QHBoxLayout()
        self.search_input = CustomSearchLineEdit()
        self.search_input.textChanged.connect(self.filter_orders)
        top_bar.addWidget(self.search_input)

        btn_pdf = QPushButton("Друк квитанції")
        btn_pdf.clicked.connect(self.generate_pdf)
        top_bar.addWidget(btn_pdf)

        btn_delete = QPushButton("Видалити")
        btn_delete.setStyleSheet("background-color: #f44336; color: white;")
        btn_delete.clicked.connect(self.delete_order)
        top_bar.addWidget(btn_delete)

        table_layout.addLayout(top_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "ID", "Клієнт", "Телефон", "Модель", "Серійний №", 
            "Статус", "Дата прийому", "Дата продажу", "Опис несправності", "Ціна", "Примітки"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemChanged.connect(self.auto_save_cell)
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)

        table_layout.addWidget(self.table)

        splitter.addWidget(form_widget)
        splitter.addWidget(table_widget)
        splitter.setSizes([350, 850])

        main_layout.addWidget(splitter)

    # --- Метод сортування та завантаження даних ---
    def load_orders(self):
        self.is_loading = True
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM service_orders")
        orders = cursor.fetchall()

        # Покращений ключ сортування за вашою вимовою
        def get_order_priority(order):
            order_id = order[0]
            status = str(order[5]) if order[5] else ""
            date_accepted_str = str(order[6]) if order[6] else ""

            is_overdue = False
            if status not in ("Готово", "Видано") and date_accepted_str:
                try:
                    if "." in date_accepted_str:
                        accepted_date = datetime.strptime(date_accepted_str, "%d.%m.%Y").date()
                    else:
                        accepted_date = datetime.strptime(date_accepted_str, "%Y-%m-%d").date()

                    if (date.today() - accepted_date).days > 14:
                        is_overdue = True
                except Exception:
                    pass

            # Визначення пріоритетів:
            if is_overdue:
                priority = 0  # 1. Прострочені (Червоний) -> НА САМИЙ ПОЧАТОК
            elif status == "Готово":
                priority = 1  # 2. Готово (Зелений) -> ПІСЛЯ ЧЕРВОНИХ
            elif status != "Видано":
                priority = 2  # 3. В роботі / Інші (Стандартні)
            else:
                priority = 3  # 4. Видано (Синій/Сірий) -> ОПУСКАЮТЬСЯ В КІНЕЦЬ

            return (priority, -order_id)

        sorted_orders = sorted(orders, key=get_order_priority)

        self.table.setRowCount(0)
        for row_idx, order in enumerate(sorted_orders):
            self.table.insertRow(row_idx)

            status = order[5]
            date_accepted_str = order[6]

            # Перевірка на прострочення для підсвітки
            is_overdue = False
            if status not in ("Готово", "Видано") and date_accepted_str:
                try:
                    if "." in date_accepted_str:
                        acc_date = datetime.strptime(date_accepted_str, "%d.%m.%Y").date()
                    else:
                        acc_date = datetime.strptime(date_accepted_str, "%Y-%m-%d").date()
                    if (date.today() - acc_date).days > 14:
                        is_overdue = True
                except Exception:
                    pass

            # Вибір кольору підсвічування
            bg_color = None
            if is_overdue:
                bg_color = QColor(255, 200, 200)  # Червоний
            elif status == "Готово":
                bg_color = QColor(200, 255, 200)  # Зелений
            elif status == "Видано":
                bg_color = QColor(220, 230, 242)  # Синій / Сірий

            for col_idx, value in enumerate(order):
                item = QTableWidgetItem(str(value) if value is not None else "")
                if bg_color:
                    item.setBackground(bg_color)
                
                # ID не можна редагувати безпосередньо у таблиці
                if col_idx == 0:
                    item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)

                self.table.setItem(row_idx, col_idx, item)

        self.is_loading = False

    def filter_orders(self, text):
        search_str = text.lower()
        for row in range(self.table.rowCount()):
            match = False
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item and search_str in item.text().lower():
                    match = True
                    break
            self.table.setRowHidden(row, not match)

    def add_order(self):
        client = self.input_client.text().strip()
        phone = self.input_phone.text().strip()
        model = self.input_model.text().strip()
        serial = self.input_serial.text().strip()
        status = self.combo_status.currentText()
        date_acc = self.input_date_accepted.date().toString("yyyy-MM-dd")
        
        date_sale = ""
        if self.input_date_sale.date() > QDate(2000, 1, 1):
            date_sale = self.input_date_sale.date().toString("yyyy-MM-dd")

        issue = self.input_issue.toPlainText().strip()
        try:
            cost = float(self.input_cost.text().replace(',', '.')) if self.input_cost.text() else 0.0
        except ValueError:
            cost = 0.0
        notes = self.input_notes.toPlainText().strip()

        if not client or not model:
            QMessageBox.warning(self, "Помилка", "Заповніть обов'язкові поля (ПІБ та Модель)!")
            return

        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO service_orders (client_name, phone, tool_model, serial_num, status, date_accepted, date_sale, issue_description, cost, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (client, phone, model, serial, status, date_acc, date_sale, issue, cost, notes))
        self.conn.commit()

        # Очищення полів
        self.input_client.clear()
        self.input_phone.clear()
        self.input_model.clear()
        self.input_serial.clear()
        self.input_issue.clear()
        self.input_cost.clear()
        self.input_notes.clear()

        self.load_orders()

    def auto_save_cell(self, item):
        if self.is_loading:
            return

        row = item.row()
        col = item.column()
        new_val = item.text().strip()
        order_id = int(self.table.item(row, 0).text())

        columns_map = {
            1: "client_name", 2: "phone", 3: "tool_model", 4: "serial_num",
            5: "status", 6: "date_accepted", 7: "date_sale", 8: "issue_description",
            9: "cost", 10: "notes"
        }

        if col in columns_map:
            col_name = columns_map[col]
            cursor = self.conn.cursor()
            cursor.execute(f"UPDATE service_orders SET {col_name} = ? WHERE id = ?", (new_val, order_id))
            self.conn.commit()
            
            # Якщо змінили статус або дату — оновлюємо таблицю для пересортування
            if col in (5, 6):
                self.load_orders()

    def on_cell_double_clicked(self, row, col):
        if col == 0:  # Подвійний клік на ID відкриває картку
            order_id = int(self.table.item(row, 0).text())
            dlg = OrderDetailsDialog(order_id, self.conn, self)
            dlg.exec()
            self.load_orders()

    def delete_order(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Увага", "Оберіть замовлення для видалення!")
            return

        order_id = int(self.table.item(row, 0).text())
        reply = QMessageBox.question(self, "Видалення", f"Перемістити замовлення №{order_id} в кошик?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM service_orders WHERE id = ?", (order_id,))
            order = cursor.fetchone()

            if order:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("""
                    INSERT INTO deleted_orders (id, client_name, phone, tool_model, serial_num, status, date_accepted, date_sale, issue_description, cost, notes, date_deleted, reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (*order, now_str, "Видалено користувачем"))

                cursor.execute("DELETE FROM service_orders WHERE id = ?", (order_id,))
                self.conn.commit()
                self.load_orders()

    def open_trash(self):
        dlg = TrashDialog(self.conn, self)
        dlg.exec()

    # --- Друк PDF-квитанції (ReportLab) ---
    def generate_pdf(self):
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.warning(self, "Увага", "Оберіть замовлення для друку квитанції!")
            return

        order_id = self.table.item(row, 0).text()
        client = self.table.item(row, 1).text()
        phone = self.table.item(row, 2).text()
        model = self.table.item(row, 3).text()
        serial = self.table.item(row, 4).text()
        date_acc = self.table.item(row, 6).text()
        issue = self.table.item(row, 8).text()

        pdf_filename = f"Квитанція_{order_id}.pdf"
        doc = SimpleDocTemplate(pdf_filename, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        
        font_name = setup_pdf_fonts()
        styles = getSampleStyleSheet()

        normal_style = ParagraphStyle('NormalStyle', parent=styles['Normal'], fontName=font_name, fontSize=10, leading=13)
        header_style = ParagraphStyle('HeaderStyle', parent=styles['Heading1'], fontName=font_name, fontSize=14, leading=16, alignment=1)

        elements = []
        elements.append(Paragraph("<b>СЕРВІСНИЙ ЦЕНТР «БЕНЗО ІНСТРУМЕНТ»</b>", header_style))
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(f"<b>АКТ-КВИТАНЦІЯ ПРИЙОМУ № {order_id}</b> від {date_acc}", header_style))
        elements.append(Spacer(1, 15))

        data = [
            [Paragraph("<b>Клієнт:</b>", normal_style), Paragraph(client, normal_style)],
            [Paragraph("<b>Телефон:</b>", normal_style), Paragraph(phone, normal_style)],
            [Paragraph("<b>Модель інструменту:</b>", normal_style), Paragraph(model, normal_style)],
            [Paragraph("<b>Заводський / Серійний №:</b>", normal_style), Paragraph(serial, normal_style)],
            [Paragraph("<b>Опис несправності:</b>", normal_style), Paragraph(issue, normal_style)],
        ]

        t = Table(data, colWidths=[160, 360])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('PADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 20))

        text_rules = """
        <b>Умови обслуговування:</b><br/>
        1. Сервісний центр не несе відповідальності за приховані дефекти, виявлені під час ремонту.<br/>
        2. Видача інструменту проводиться тільки при наявності даної квитанції.<br/>
        3. Запчастини, замінені під час ремонту, повертаються за вимогою клієнта.
        """
        elements.append(Paragraph(text_rules, normal_style))
        elements.append(Spacer(1, 30))

        signatures = [
            [Paragraph("Замовник: _________________", normal_style), Paragraph("Прийняв: _________________", normal_style)]
        ]
        t_sig = Table(signatures, colWidths=[260, 260])
        elements.append(t_sig)

        try:
            doc.build(elements)
            QMessageBox.information(self, "Успіх", f"Квитанцію збережено у файл:\n{pdf_filename}")
            os.startfile(pdf_filename)
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося згенерувати PDF:\n{str(e)}")

    # --- Підтримка Drag & Drop для фотографій ---
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        pos = event.position().toPoint()
        row = self.table.rowAt(self.table.mapFromGlobal(self.mapToGlobal(pos)).y() - self.table.header().height())

        if row >= 0:
            order_id = int(self.table.item(row, 0).text())
            files = [url.toLocalFile() for url in event.mimeData().urls() if url.toLocalFile().lower().endswith(('.png', '.jpg', '.jpeg'))]

            if files:
                app_dir = os.path.dirname(os.path.abspath(__file__))
                photos_dir = os.path.join(app_dir, "photos")
                os.makedirs(photos_dir, exist_ok=True)

                cursor = self.conn.cursor()
                for file_path in files:
                    ext = os.path.splitext(file_path)[1]
                    new_filename = f"order_{order_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{ext}"
                    dest_path = os.path.join(photos_dir, new_filename)

                    with open(file_path, 'rb') as src, open(dest_path, 'wb') as dst:
                        dst.write(src.read())

                    cursor.execute("INSERT INTO order_photos (order_id, photo_path) VALUES (?, ?)", (order_id, dest_path))

                self.conn.commit()
                QMessageBox.information(self, "Успіх", f"До замовлення №{order_id} додано {len(files)} фото!")

    def closeEvent(self, event):
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = ServiceManagerApp()
    window.show()
    sys.exit(app.exec())
