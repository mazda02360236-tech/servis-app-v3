from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QHeaderView, QTableWidget


class OrderTableManager:

    def __init__(self, table: QTableWidget):
        self.table = table
        self.settings = QSettings("YourCompany", "ServiceManagerApp")

        self.setup_resizable_columns()
        self.load_table_layout()

    def setup_resizable_columns(self):
        # Дозволяємо користувачу змінювати ширину колонок та висоту рядків
        h_header = self.table.horizontalHeader()
        v_header = self.table.verticalHeader()

        h_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        v_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        # Автоматичне збереження при кожній зміні розміру колонки чи рядка
        h_header.sectionResized.connect(self.save_table_layout)
        v_header.sectionResized.connect(self.save_table_layout)

    def save_table_layout(self):
        # Зберігаємо точний стан (ширину колонок та порядок)
        self.settings.setValue(
            "orders_table/h_state", self.table.horizontalHeader().saveState()
        )
        self.settings.setValue(
            "orders_table/v_state", self.table.verticalHeader().saveState()
        )

    def load_table_layout(self):
        # Відновлюємо збережений стан при запуску
        h_state = self.settings.value("orders_table/h_state")
        v_state = self.settings.value("orders_table/v_state")

        if h_state:
            self.table.horizontalHeader().restoreState(h_state)
        if v_state:
            self.table.verticalHeader().restoreState(v_state)
