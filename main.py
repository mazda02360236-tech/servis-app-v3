import json
import os
import tkinter as tk
from tkinter import ttk


class ServiceCenterApp:

    def __init__(self, root):
        self.root = root
        self.root.title("Управління замовленнями сервісного центру")
        self.root.geometry("1100x600")

        self.config_file = "table_config.json"

        # Колонки таблиці
        self.columns = (
            "num",
            "date",
            "client",
            "phone",
            "device",
            "issue",
            "status",
            "price",
        )
        self.headers = {
            "num": "№ Замовлення",
            "date": "Дата",
            "client": "Клієнт",
            "phone": "Телефон",
            "device": "Пристрій",
            "issue": "Несправність",
            "status": "Статус",
            "price": "Сума (грн)",
        }

        # Стандартні розміри колонок за замовчуванням
        self.default_widths = {
            "num": 100,
            "date": 100,
            "client": 150,
            "phone": 130,
            "device": 140,
            "issue": 230,
            "status": 110,
            "price": 100,
        }

        self.init_ui()
        self.load_column_widths()

        # Збереження розмірів при відпусканні миші або закритті вікна
        self.tree.bind("<ButtonRelease-1>", self.save_column_widths)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def init_ui(self):
        # Створення таблиці
        self.tree = ttk.Treeview(
            self.root, columns=self.columns, show="headings"
        )

        for col in self.columns:
            self.tree.heading(col, text=self.headers[col])
            self.tree.column(
                col, width=self.default_widths[col], anchor="center"
            )

        # Скроллбар
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
                "Чистка після рідини",
                "Діагностика",
                "1800",
            ),
        ]
        for row in sample_data:
            self.tree.insert("", "end", values=row)

    def save_column_widths(self, event=None):
        """Зберігає поточну ширину всіх колонок у JSON файл."""
        widths = {}
        for col in self.columns:
            widths[col] = self.tree.column(col, "width")

        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(widths, f, ensure_ascii=False, indent=4)
        except Exception:
            pass

    def load_column_widths(self):
        """Завантажує збережені розміри колонок при запуску."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    widths = json.load(f)
                    for col, width in widths.items():
                        if col in self.columns:
                            self.tree.column(col, width=int(width))
            except Exception:
                pass

    def on_close(self):
        self.save_column_widths()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ServiceCenterApp(root)
    root.mainloop()
