import sys
import os
import sqlite3
import shutil
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QComboBox, QDialog, QFileDialog, 
    QStyledItemDelegate, QAbstractItemView, QStyle
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QColor

class StatusDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        # Если строка выделена — отображаем стандартный цвет выделения всей строки
        if option.state & QStyle.StateFlag.State_Selected:
            option.backgroundBrush = QColor("#007bff")
            super().paint(painter, option, index)
            return

        # Иначе красим статус в его цвет
        status = index.data()
        if status == "В роботі":
            option.backgroundBrush = QColor("#d4edda")
        elif status == "Готово":
            option.backgroundBrush = QColor("#cce5ff")
        elif status == "Видано":
            option.backgroundBrush = QColor("#e2e3e5")
        elif status == "Очікує запчастини":
            option.backgroundBrush = QColor("#fff3cd")
        elif status == "Відмова":
            option.backgroundBrush = QColor("#f8d7da")
        
        super().paint(painter, option, index)

class ServiceApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Сервісний Центр v3.0")
        self.setGeometry(100, 100, 1280, 720)
        
        self.db_name = "service.db"
        self.init_db()
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # --- ЛЕВАЯ ПАНЕЛЬ ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setFixedWidth(320)
        
        left_layout.addWidget(QLabel("<b>Нове замовлення / Редагування</b>"))
        
        self.input_client = QLineEdit()
        self.input_client.setPlaceholderText("ПІБ Клієнта")
        left_layout.addWidget(self.input_client)
        
        self.input_phone = QLineEdit()
        self.input_phone.setPlaceholderText("Телефон")
        left_layout.addWidget(self.input_phone)
        
        self.input_device = QLineEdit()
        self.input_device.setPlaceholderText("Пристрій (напр. iPhone 11)")
        left_layout.addWidget(self.input_device)
        
        self.input_defect = QLineEdit()
        self.input_defect.setPlaceholderText("Несправність")
        left_layout.addWidget(self.input_defect)
        
        self.input_price = QLineEdit()
        self.input_price.setPlaceholderText("Ціна (грн)")
        left_layout.addWidget(self.input_price)
        
        self.combo_status = QComboBox()
        self.combo_status.addItems(["В роботі", "Очікує запчастини", "Готово", "Видано", "Відмова"])
        left_layout.addWidget(self.combo_status)
        
        self.btn_photo = QPushButton("📷 Додати фото")
        self.btn_photo.clicked.connect(self.select_photo)
        left_layout.addWidget(self.btn_photo)
        self.selected_photo_path = None
        
        self.btn_add = QPushButton("Зберегти замовлення")
        self.btn_add.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 6px;")
        self.btn_add.clicked.connect(self.save_order)
        left_layout.addWidget(self.btn_add)
        
        self.btn_clear = QPushButton("Очистити форму")
        self.btn_clear.clicked.connect(self.clear_form)
        left_layout.addWidget(self.btn_clear)
        
        left_layout.addStretch()
        
        # --- ПРАВАЯ ПАНЕЛЬ ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        filter_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Пошук за квитанцією, ПІБ, телефоном або пристроєм...")
        self.search_input.textChanged.connect(self.load_orders)
        filter_layout.addWidget(self.search_input)
        
        right_layout.addLayout(filter_layout)
        
        # Таблица заказов
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "№ Квитанції", "Дата", "Клієнт", "Телефон", "Пристрій", "Несправність", "Статус", "Фото"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # Включаем подсвечивание всей строки от левого до правого края
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        # Принудительный стиль синей подсветки выделенной строки
        self.table.setStyleSheet("""
            QTableWidget {
                gridline-color: #d6d6d6;
                selection-background-color: #007bff;
                selection-color: #ffffff;
            }
            QTableWidget::item:selected {
                background-color: #007bff !important;
                color: #ffffff !important;
            }
        """)
        
        # Делегат статуса
        self.table.setItemDelegateForColumn(6, StatusDelegate(self.table))
        
        # Обработка клика по ячейкам
        self.table.cellClicked.connect(self.on_cell_clicked)
        
        right_layout.addWidget(self.table)
        
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel)
        
        self.load_orders()

    def init_db(self):
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                client TEXT,
                phone TEXT,
                device TEXT,
                defect TEXT,
                price REAL,
                status TEXT,
                photo_path TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def select_photo(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Оберіть фотографію", "", "Зображення (*.png *.jpg *.jpeg)")
        if file_path:
            self.selected_photo_path = file_path
            self.btn_photo.setText("📷 Фото обрано")

    def save_order(self):
        client = self.input_client.text().strip()
        phone = self.input_phone.text().strip()
        device = self.input_device.text().strip()
        defect = self.input_defect.text().strip()
        price = self.input_price.text().strip()
        status = self.combo_status.currentText()
        
        if not client or not device:
            QMessageBox.warning(self, "Помилка", "Заповніть обов'язкові поля (Клієнт, Пристрій)!")
            return
            
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        saved_photo_path = ""
        if self.selected_photo_path:
            if not os.path.exists("photos"):
                os.makedirs("photos")
            filename = f"photo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            saved_photo_path = os.path.join("photos", filename)
            shutil.copy(self.selected_photo_path, saved_photo_path)
            
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO orders (date, client, phone, device, defect, price, status, photo_path)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (date_str, client, phone, device, defect, price, status, saved_photo_path))
        conn.commit()
        conn.close()
        
        self.clear_form()
        self.load_orders()
        QMessageBox.information(self, "Успіх", "Замовлення успішно збережено!")

    def clear_form(self):
        self.input_client.clear()
        self.input_phone.clear()
        self.input_device.clear()
        self.input_defect.clear()
        self.input_price.clear()
        self.combo_status.setCurrentIndex(0)
        self.selected_photo_path = None
        self.btn_photo.setText("📷 Додати фото")

    def load_orders(self):
        search = self.search_input.text().strip()
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        if search:
            query = '''
                SELECT id, date, client, phone, device, defect, status, photo_path 
                FROM orders 
                WHERE id LIKE ? OR client LIKE ? OR phone LIKE ? OR device LIKE ?
                ORDER BY id DESC
            '''
            s_param = f"%{search}%"
            cursor.execute(query, (s_param, s_param, s_param, s_param))
        else:
            cursor.execute('SELECT id, date, client, phone, device, defect, status, photo_path FROM orders ORDER BY id DESC')
            
        rows = cursor.fetchall()
        conn.close()
        
        self.table.setRowCount(0)
        for row_idx, row_data in enumerate(rows):
            self.table.insertRow(row_idx)
            
            # Заполняем текстовые колонки
            for col_idx in range(7):
                item = QTableWidgetItem(str(row_data[col_idx]))
                # Корректная установка флагов: делаем ячейку выделяемой, но не редактируемой
                flags = (item.flags() & ~Qt.ItemFlag.ItemIsEditable) | Qt.ItemFlag.ItemIsSelectable
                item.setFlags(flags)
                self.table.setItem(row_idx, col_idx, item)
            
            # Колонка "Фото" (индекс 7)
            photo_path = row_data[7]
            photo_item = QTableWidgetItem()
            flags = (photo_item.flags() & ~Qt.ItemFlag.ItemIsEditable) | Qt.ItemFlag.ItemIsSelectable
            photo_item.setFlags(flags)
            
            if photo_path and os.path.exists(photo_path):
                photo_item.setText("📷 Перегляд")
                photo_item.setData(Qt.ItemDataRole.UserRole, photo_path)
            else:
                photo_item.setText("—")
                photo_item.setData(Qt.ItemDataRole.UserRole, None)
                
            self.table.setItem(row_idx, 7, photo_item)

    def on_cell_clicked(self, row, column):
        # Просмотр фото срабатывает только при клике на 7-ю колонку ("Фото")
        if column != 7:
            return
            
        item = self.table.item(row, column)
        if not item:
            return
            
        photo_path = item.data(Qt.ItemDataRole.UserRole)
        
        if photo_path and os.path.exists(photo_path):
            order_id = self.table.item(row, 0).text()
            self.show_photo_dialog(order_id, photo_path, row)

    def show_photo_dialog(self, order_id, photo_path, row):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Перегляд фото — Замовлення №{order_id}")
        dialog.setMinimumSize(500, 500)
        layout = QVBoxLayout(dialog)

        # Просмотр фото
        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(photo_path)
        if not pixmap.isNull():
            label.setPixmap(pixmap.scaled(580, 580, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            label.setText("Помилка завантаження зображення")
        layout.addWidget(label)

        # Кнопка удаления фото
        btn_delete = QPushButton("🗑️ Видалити фото")
        btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #dc3545; 
                color: white; 
                font-weight: bold; 
                padding: 10px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #bd2130;
            }
        """)
        layout.addWidget(btn_delete)

        def delete_photo():
            reply = QMessageBox.question(
                dialog, 
                "Підтвердження", 
                "Ви дійсно бажаєте видалити це фото?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                # 1. Удаление файла с диска
                try:
                    if os.path.exists(photo_path):
                        os.remove(photo_path)
                except Exception as e:
                    QMessageBox.warning(dialog, "Помилка", f"Не вдалося видалити файл: {e}")

                # 2. Обновление записи в БД
                conn = sqlite3.connect(self.db_name)
                cursor = conn.cursor()
                cursor.execute("UPDATE orders SET photo_path = '' WHERE id = ?", (order_id,))
                conn.commit()
                conn.close()

                # 3. Обновление ячейки в таблице
                item = self.table.item(row, 7)
                item.setText("—")
                item.setData(Qt.ItemDataRole.UserRole, None)

                QMessageBox.information(dialog, "Успіх", "Фотографію успішно видалено!")
                dialog.accept()

        btn_delete.clicked.connect(delete_photo)
        dialog.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ServiceApp()
    window.show()
    sys.exit(app.exec())
