import sys
import os
import sqlite3
import shutil
from datetime import datetime
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QComboBox, QDialog, QFileDialog, 
    QAbstractItemView
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QColor

class ServiceApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Сервісний Центр v3.0")
        self.setGeometry(100, 100, 1280, 720)
        
        self.db_name = "service.db"
        self.statuses = ["В роботі", "Очікує запчастини", "Готово", "Видано", "Відмова"]
        self.init_db()
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # --- ЛІВА ПАНЕЛЬ ---
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
        self.combo_status.addItems(self.statuses)
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
        
        # --- ПРАВА ПАНЕЛЬ ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        filter_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Пошук за квитанцією, ПІБ, телефоном або пристроєм...")
        self.search_input.textChanged.connect(self.load_orders)
        filter_layout.addWidget(self.search_input)
        
        right_layout.addLayout(filter_layout)
        
        # Таблиця замовлень
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "№ Квитанції", "Дата", "Клієнт", "Телефон", "Пристрій", "Несправність", "Статус", "Фото"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # Виділення всього рядка
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
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
        
        # Обробка кліку по комірках
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

    def get_status_style(self, status):
        styles = {
            "В роботі": "background-color: #d4edda; color: #155724; font-weight: bold; border: none; padding: 2px;",
            "Готово": "background-color: #cce5ff; color: #004085; font-weight: bold; border: none; padding: 2px;",
            "Видано": "background-color: #e2e3e5; color: #383d41; font-weight: bold; border: none; padding: 2px;",
            "Очікує запчастини": "background-color: #fff3cd; color: #856404; font-weight: bold; border: none; padding: 2px;",
            "Відмова": "background-color: #f8d7da; color: #721c24; font-weight: bold; border: none; padding: 2px;",
        }
        return styles.get(status, "")

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
            order_id = row_data[0]
            
            # Поля з 0 по 5
            for col_idx in range(6):
                item = QTableWidgetItem(str(row_data[col_idx]))
                flags = (item.flags() & ~Qt.ItemFlag.ItemIsEditable) | Qt.ItemFlag.ItemIsSelectable
                item.setFlags(flags)
                self.table.setItem(row_idx, col_idx, item)
            
            # Колонка 6: СТАТУС (зміна безпосередньо у рядку замовлення)
            status_combo = QComboBox()
            status_combo.addItems(self.statuses)
            current_status = row_data[6]
            if current_status in self.statuses:
                status_combo.setCurrentText(current_status)
            status_combo.setStyleSheet(self.get_status_style(current_status))
            
            # Сигнал зміни статусу в таблиці
            status_combo.currentTextChanged.connect(
                lambda new_status, oid=order_id, r=row_idx, cb=status_combo: self.on_status_changed(oid, new_status, r, cb)
            )
            self.table.setCellWidget(row_idx, 6, status_combo)
            
            # Колонка 7: ФОТО
            photo_path = row_data[7]
            photo_item = QTableWidgetItem()
            flags = (photo_item.flags() & ~Qt.ItemFlag.ItemIsEditable) | Qt.ItemFlag.ItemIsSelectable
            photo_item.setFlags(flags)
            
            if photo_path and os.path.exists(photo_path):
                photo_item.setText("📷 Відкрити фото")
                photo_item.setData(Qt.ItemDataRole.UserRole, photo_path)
                photo_item.setForeground(QColor("#007bff"))
            else:
                photo_item.setText("—")
                photo_item.setData(Qt.ItemDataRole.UserRole, None)
                
            self.table.setItem(row_idx, 7, photo_item)

    def on_status_changed(self, order_id, new_status, row_idx, combo):
        combo.setStyleSheet(self.get_status_style(new_status))
        self.table.selectRow(row_idx)
        
        # Миттєве збереження в БД
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
        conn.commit()
        conn.close()

    def on_cell_clicked(self, row, column):
        self.table.selectRow(row)
        
        # Перегляд фото при кліку на колонку 7
        if column == 7:
            item = self.table.item(row, column)
            if not item:
                return
            photo_path = item.data(Qt.ItemDataRole.UserRole)
            if photo_path and os.path.exists(photo_path):
                order_id = self.table.item(row, 0).text()
                self.show_photo_dialog(order_id, photo_path, row)
            else:
                QMessageBox.information(self, "Інформація", "У цьому замовленні немає доданого фото.")

    def show_photo_dialog(self, order_id, photo_path, row):
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Перегляд фото — Замовлення №{order_id}")
        dialog.setMinimumSize(500, 500)
        layout = QVBoxLayout(dialog)

        label = QLabel()
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(photo_path)
        if not pixmap.isNull():
            label.setPixmap(pixmap.scaled(580, 580, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            label.setText("Помилка завантаження зображення")
        layout.addWidget(label)

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
                try:
                    if os.path.exists(photo_path):
                        os.remove(photo_path)
                except Exception as e:
                    QMessageBox.warning(dialog, "Помилка", f"Не вдалося видалити файл: {e}")

                conn = sqlite3.connect(self.db_name)
                cursor = conn.cursor()
                cursor.execute("UPDATE orders SET photo_path = '' WHERE id = ?", (order_id,))
                conn.commit()
                conn.close()

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
