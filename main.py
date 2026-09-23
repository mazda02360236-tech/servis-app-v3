import json
import os
import tkinter as tk
from tkinter import ttk


class ServiceCenterApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Управління замовленнями сервісного центру")
        self.root.geometry("1200x600")

        self.config_file = "table_config.json"
        self.data_file = "orders_data.json"

        # Колонки таблиці
        self.columns = (
            "id",
            "client",
            "phone",
            "date_sale",
            "date_in",
            "date_out",
            "device",
            "serial",
            "kit",
            "issue",
            "status",
        )
        self.headers = {
            "id": "ID",
            "client": "Клієнт",
            "phone": "Телефон",
            "date_sale": "Дата продажу",
            "date_in": "Дата прийому",
            "date_out": "Дата видачі",
            "device": "Товар",
            "serial": "Серійний №",
            "kit": "Комплектація",
            "issue": "Несправність",
            "status": "Статус",
        }

        self.default_widths = {
            "id": 40,
            "client": 110,
            "phone": 110,
            "date_sale": 90,
            "date_in": 90,
            "date_out": 90,
            "device": 130,
            "serial": 100,
            "kit": 110,
            "issue": 140,
            "status": 90,
        }

        self.init_ui()
        self.load_column_widths()

        # Події для збереження ширини та редагування комірок
        self.tree.bind("<ButtonRelease-1>", self.save_column_widths)
        self.tree.bind("<Double-1>", self.on_double_click_cell)

    def init_ui(self):
        self.tree = ttk.Treeview(
            self.root, columns=self.columns, show="headings"
        )

        for col in self.columns:
            self.tree.heading(col, text=self.headers[col])
            self.tree.column(
                col, width=self.default_widths[col], anchor="center"
            )

        scrollbar = ttk.Scrollbar(
            self.root, orient="vertical", command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(
            side="left", fill="both", expand=True, padx=10, pady=10
        )
        scrollbar.pack(side="right", fill="y", pady=10)

        self.add_sample_data()

    def add_sample_data(self):
        sample_data = [
            (
                "40",
                "Володимир",
                "0988571802",
                "14.03.2026",
                "23.09.2026",
                "23.12.2026",
                "Шліфмашинка...",
                "00242724",
                "тушка",
                "не працює",
                "В роботі",
            ),
            (
                "39",
                "Віталій",
                "0970559359",
                "25.08.2026",
                "23.09.2026",
                "23.12.2026",
                "гвинтоверт...",
                "102907008",
                "тушка",
                "не працює",
                "В роботі",
            ),
            (
                "38",
                "Єгор",
                "0681998750",
                "10.09.2026",
                "22.09.2026",
                "22.12.2026",
                "Гравіювальна...",
                "00956624",
                "без документів",
                "зігнутий вал",
                "В роботі",
            ),
        ]
        for row in sample_data:
            self.tree.insert("", "end", values=row)

    def on_double_click_cell(self, event):
        """Функція редагування комірки за подвійним кліком."""
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        column = self.tree.identify_column(event.x)
        row_id = self.tree.identify_row(event.y)

        # Визначаємо номер колонки (наприклад, '#1' -> 0)
        col_index = int(column.replace("#", "")) - 1

        # За бажанням, можна заборонити редагувати ID (копирка 0):
        # if col_index == 0:
        #     return

        # Отримуємо геометрію та поточне значення комірки
        x, y, w, h = self.tree.bbox(row_id, column)
        current_values = list(self.tree.item(row_id, "values"))
        current_value = current_values[col_index]

        # Створюємо тимчасове поле введення поверх комірки
        entry = tk.Entry(self.tree)
        entry.place(x=x, y=y, width=w, height=h)
        entry.insert(0, current_value)
        entry.select_range(0, tk.END)
        entry.focus()

        def save_cell_value(e=None):
            new_value = entry.get()
            current_values[col_index] = new_value
            self.tree.item(row_id, values=current_values)
            entry.destroy()

        entry.bind("<Return>", save_cell_value)
        entry.bind("<FocusOut>", lambda e: entry.destroy())

    def save_column_widths(self, event=None):
        widths = {col: self.tree.column(col, "width") for col in self.columns}
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(widths, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def load_column_widths(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    widths = json.load(f)
                    for col, width in widths.items():
                        if col in self.columns:
                            self.tree.column(col, width=int(width))
            except Exception:
                pass


if __name__ == "__main__":
    root = tk.Tk()
    app = ServiceCenterApp(root)
    root.mainloop()
