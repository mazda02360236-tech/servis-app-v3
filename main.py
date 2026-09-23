import sys
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ServiceCenterApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Управління замовленнями сервісного центру")
        self.resize(1150, 600)

        # Налаштування сховища параметрів (QSettings)
        self.settings = QSettings("ServiceCenterApp", "OrderTableSettings")

        self.init_ui()
        # Завантажуємо збережені розміри після створення UI
        self.load_table_layout()

    def init_ui(self):
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)

        # Створення таблиці
        self.table = QTableWidget()

        # Колонки таблиці замовлень
        headers = [
            "№ Замовлення",
            "Дата",
            "Клієнт",
            "Телефон",
            "Пристрій",
            "Несправність",
            "Статус",
            "Сума (грн)",
        ]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)

        # Отримуємо заголовки таблиці
        h_header = self.table.horizontalHeader()
        v_header = self.table.verticalHeader()

        # Вмикаємо інтерактивний режим зміни розмірів для користувача
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        v_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        # Підключаємо автозбереження при кожному перетягуванні межі колонки або рядка
        h_header.sectionResized.connect(self.save_table_layout)
        v_header.sectionResized.connect(self.save_table_layout)

        # Додавання тестових даних
        self.add_sample_data()

        layout.addWidget(self.table)
        self.setCentralWidget(central_widget)

    def add_sample_data(self):
        sample_orders = [
            (
                "1001",
                "23.09.2026",
                "Іван Петренко",
                "+380971234567",
                "iPhone 13",
                "Заміна дисплея та акумулятора",
                "В роботі",
                "4500",
            ),
            (
                "1002",
                "23.09.2026",
                "Марія Сидорова",
                "+380509876543",
                "MacBook Air M1",
                "Чистка після потрапляння рідини",
                "Диагностика",
                "1800",
            ),
        ]

        self.table.setRowCount(len(sample_orders))
        for row, order in enumerate(sample_orders):
            for col, value in enumerate(order):
                item = QTableWidgetItem(value)
                if col in [0, 1, 7]:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

    def save_table_layout(self):
        """Автоматично зберігає стан ширини колонок та висоти рядків."""
        h_state = self.table.horizontalHeader().saveState()
        v_state = self.table.verticalHeader().saveState()

        self.settings.setValue("table/h_state", h_state)
        self.settings.setValue("table/v_state", v_state)

    def load_table_layout(self):
        """Відновлює збережений стан колонок та рядків при запуску."""
        h_state = self.settings.value("table/h_state")
        v_state = self.settings.value("table/v_state")

        if h_state:
            self.table.horizontalHeader().restoreState(h_state)
        if v_state:
            self.table.verticalHeader().restoreState(v_state)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ServiceCenterApp()
    window.show()
    sys.exit(app.exec())
