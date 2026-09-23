from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QApplication,
    QHeaderView,
    QMainWindow,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class OrderTableManager:
    """Менеджер автозбереження розмірів колонок та рядків таблиці замовлень."""

    def __init__(
        self, table: QTableWidget, app_name: str = "ServiceCenterApp"
    ):
        self.table = table
        self.settings = QSettings("ServiceCenter", app_name)

        self.setup_resizable_headers()
        self.load_table_layout()

    def setup_resizable_headers(self):
        h_header = self.table.horizontalHeader()
        v_header = self.table.verticalHeader()

        # Дозволяємо користувачу інтерактивно змінювати ширину колонок і висоту рядків
        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        v_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        # Автоматичне збереження при кожній зміні розміру користувачем
        h_header.sectionResized.connect(self.save_table_layout)
        v_header.sectionResized.connect(self.save_table_layout)

    def save_table_layout(self):
        # Зберігаємо точний стан заголовків (ширина колонок, висота рядків, порядок)
        self.settings.setValue(
            "orders_table/h_state", self.table.horizontalHeader().saveState()
        )
        self.settings.setValue(
            "orders_table/v_state", self.table.verticalHeader().saveState()
        )

    def load_table_layout(self):
        # Відновлюємо збережені розміри при запуску програми
        h_state = self.settings.value("orders_table/h_state")
        v_state = self.settings.value("orders_table/v_state")

        if h_state:
            self.table.horizontalHeader().restoreState(h_state)
        if v_state:
            self.table.verticalHeader().restoreState(v_state)


class ServiceCenterMainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Облік замовлень сервісного центру")
        self.resize(1100, 600)

        # 1. Ініціалізація таблиці замовлень
        self.table = QTableWidget()
        columns = [
            "№ Замовлення",
            "Дата",
            "Клієнт",
            "Телефон",
            "Пристрій",
            "Несправність",
            "Статус",
            "Сума (грн)",
        ]
        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)

        # Тестовий рядок
        self.table.setRowCount(1)
        sample_data = [
            "1001",
            "23.09.2026",
            "Іван Петренко",
            "+380971234567",
            "iPhone 13",
            "Заміна дисплея та акумулятора",
            "В роботі",
            "4500",
        ]
        for col, val in enumerate(sample_data):
            self.table.setItem(0, col, QTableWidgetItem(val))

        # 2. Підключення менеджера автозбереження розмірів
        self.table_manager = OrderTableManager(
            self.table, app_name="ServiceCenterApp"
        )

        # Розміщення таблиці
        layout = QVBoxLayout()
        layout.addWidget(self.table)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)


if __name__ == "__main__":
    app = QApplication([])
    window = ServiceCenterMainWindow()
    window.show()
    app.exec()
