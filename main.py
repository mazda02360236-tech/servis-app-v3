import os
import sqlite3
import shutil
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, send_file

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DATA_DIR = os.path.join(BASE_DIR, 'ServiceManagerData')
os.makedirs(APP_DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(APP_DATA_DIR, "service_orders.db")
UPLOAD_DIR = os.path.join(APP_DATA_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

PYTHON_DATE_FORMAT = "%d.%m.%Y"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
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
            date_sale TEXT,
            first_date_in TEXT
        )
    """)
    cursor.execute("""
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
            deleted_at TEXT,
            first_date_in TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER,
            photo_path TEXT,
            FOREIGN KEY (order_id) REFERENCES orders (id) ON DELETE CASCADE
        )
    """)
    conn.commit()
    conn.close()

init_db()

def format_date_to_ukr(date_str):
    if not date_str or date_str == "None":
        return ""
    try:
        d = datetime.strptime(str(date_str), "%Y-%m-%d")
        return d.strftime("%d.%m.%Y")
    except ValueError:
        return str(date_str)

# --- PDF GENERATION VIA REPORTLAB ---
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph, Image as RLImage
from reportlab.lib.styles import ParagraphStyle

def setup_cyrillic_font():
    win_font_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'Fonts', 'arial.ttf')
    if os.path.exists(win_font_path):
        try:
            pdfmetrics.registerFont(TTFont('ArialWin', win_font_path))
            return 'ArialWin'
        except:
            pass
    return 'Helvetica'

def get_logo_path():
    for ext in ['logo.png', 'logo.jpg', 'logo.jpeg']:
        path = os.path.join(BASE_DIR, ext)
        if os.path.exists(path):
            return path
    return None

def generate_pdf_receipt(order_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        return None

    cursor.execute("SELECT photo_path FROM order_photos WHERE order_id = ?", (order_id,))
    photos = cursor.fetchall()
    conn.close()

    font_name = setup_cyrillic_font()
    logo_path = get_logo_path()

    pdf_filename = os.path.join(APP_DATA_DIR, f"Kvitantsiya_A5_{order_id}.pdf")
    c = canvas.Canvas(pdf_filename, pagesize=A4)
    width, height = A4
    half_height = height / 2

    # Рамка А5
    c.setStrokeColor(colors.HexColor("#2C3E50"))
    c.setLineWidth(1.5)
    c.rect(10, half_height + 10, width - 20, half_height - 20)

    # Шапка
    c.setFillColor(colors.HexColor("#2C3E50"))
    c.rect(10, height - 45, width - 20, 35, fill=1, stroke=0)

    text_x = 20
    if logo_path:
        try:
            c.drawImage(logo_path, 15, height - 42, width=70, height=28, preserveAspectRatio=True, mask='auto')
            text_x = 95
        except:
            pass

    c.setFillColor(colors.white)
    c.setFont(font_name, 10.5)
    status_str = order['status'] or 'В роботі'
    c.drawString(text_x, height - 30, f"АКТ-КВИТАНЦІЯ № {order_id} [{status_str}]")
    
    c.setFont(font_name, 9)
    c.drawRightString(width - 20, height - 30, f"Прийом: {format_date_to_ukr(order['date_in'])}")

    c.setFillColor(colors.black)
    y = height - 65
    c.setLineWidth(0.5)
    c.setStrokeColor(colors.HexColor("#BDC3C7"))

    c.setFont(font_name, 9.5)
    c.drawString(20, y, f"Клієнт: {order['client_name'] or '—'}")
    c.drawRightString(width - 20, y, f"Телефон: {order['phone'] or '—'}")
    
    y -= 18
    c.line(20, y + 10, width - 20, y + 10)

    c.drawString(20, y, f"Товар / Модель: {order['item_name'] or '—'}")
    c.drawString(320, y, f"Серійний №: {order['serial_num'] or '—'}")

    y -= 18
    c.drawString(20, y, f"Комплектація: {order['equipment'] or '—'}")
    c.drawString(320, y, f"Дата продажу: {format_date_to_ukr(order['date_sale']) or '—'}")

    y -= 18
    if order['first_date_in']:
        c.drawString(20, y, f"Дата 1-го ремонту: {format_date_to_ukr(order['first_date_in'])}")
        c.drawString(320, y, f"Планова видача: {format_date_to_ukr(order['date_out']) or '—'}")
        y -= 18
        c.drawString(20, y, f"Дата повторного ремонту: {format_date_to_ukr(order['date_in'])}")
    else:
        c.drawString(20, y, f"Планова дата видачі: {format_date_to_ukr(order['date_out']) or '—'}")

    y -= 15
    c.line(20, y + 10, width - 20, y + 10)

    # Несправність
    c.setFont(font_name, 9)
    issue_style = ParagraphStyle('IssueStyle', fontName=font_name, fontSize=9, leading=12, textColor=colors.black)
    issue_p = Paragraph(f"<b>Несправність:</b> {order['issue'] or '—'}", issue_style)
    issue_p.wrap(width - 40, 60)
    issue_height = issue_p.height
    issue_p.drawOn(c, 20, y - issue_height + 5)

    y -= (issue_height + 12)
    c.line(20, y + 10, width - 20, y + 10)

    # Фото
    if photos:
        c.setFont(font_name, 8)
        c.drawString(20, y, f"Прикріплені фотографії ({len(photos)}):")
        y -= 115
        photo_x = 20
        for (p_path,) in photos[:2]:
            if os.path.exists(p_path):
                try:
                    img = RLImage(p_path, width=130)
                    img.drawOn(c, photo_x, y)
                    photo_x += 145
                except:
                    pass
        y -= 10
    else:
        y -= 10

    c.setFont(font_name, 7)
    c.setFillColor(colors.HexColor("#444444"))
    notes = (
        "1. Видача здійснюється за наявності даної квитанції.\n"
        "2. Сервісний центр не відповідає за збереження даних.\n"
        "3. Готове обладнання зберігається безоплатно протягом 30 днів."
    )
    text_obj = c.beginText(20, y)
    text_obj.setLeading(9)
    for line in notes.split('\n'):
        text_obj.textLine(line)
    c.drawText(text_obj)

    y_sig = half_height + 25
    c.setFont(font_name, 8.5)
    c.setFillColor(colors.black)
    c.drawString(20, y_sig, "Замовник: _________________ (підпис)")
    c.drawRightString(width - 20, y_sig, "Прийняв: _________________ (підпис)")

    c.save()
    return pdf_filename

# --- WEB ROUTES ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <title>Облік ремонту інструменту — БЕНЗО ІНСТРУМЕНТ</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; font-size: 14px; }
        .table-container { background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .status-badge { padding: 4px 8px; border-radius: 4px; color: white; font-weight: bold; }
    </style>
</head>
<body class="container-fluid py-3">
    <div class="d-flex justify-content-between align-items-center mb-3">
        <h2>🛠️ БЕНЗО ІНСТРУМЕНТ — Сервісний Центр</h2>
        <div>
            <button class="btn btn-success btn-sm" onclick="quickOrder()">⚡ Швидке замовлення</button>
            <button class="btn btn-secondary btn-sm" onclick="openTrash()">🗑️ Кошик</button>
        </div>
    </div>

    <!-- Форма додавання -->
    <div class="card p-3 mb-3 shadow-sm">
        <h5>Нове замовлення</h5>
        <div class="row g-2">
            <div class="col-md-3"><input type="text" id="client_name" class="form-control form-control-sm" placeholder="ПІБ Клієнта"></div>
            <div class="col-md-3"><input type="text" id="phone" class="form-control form-control-sm" placeholder="Телефон"></div>
            <div class="col-md-3"><input type="text" id="item_name" class="form-control form-control-sm" placeholder="Товар / Модель"></div>
            <div class="col-md-3"><input type="text" id="serial_num" class="form-control form-control-sm" placeholder="Серійний номер"></div>
            <div class="col-md-3"><input type="text" id="equipment" class="form-control form-control-sm" placeholder="Комплектація"></div>
            <div class="col-md-3"><input type="text" id="issue" class="form-control form-control-sm" placeholder="Несправність"></div>
            <div class="col-md-2">
                <select id="status" class="form-select form-select-sm">
                    <option>В роботі</option>
                    <option>Очікує запчастин</option>
                    <option>Готово</option>
                    <option>Видано</option>
                    <option>Повторний ремонт</option>
                </select>
            </div>
            <div class="col-md-2"><input type="date" id="date_in" class="form-control form-control-sm"></div>
            <div class="col-md-2"><button class="btn btn-primary btn-sm w-100" onclick="saveOrder()">Зберегти</button></div>
        </div>
    </div>

    <!-- Пошук -->
    <div class="mb-3">
        <input type="text" id="search" class="form-control" placeholder="🔍 Пошук по клієнту, телефону, товару..." oninput="loadOrders()">
    </div>

    <!-- Таблиця -->
    <div class="table-container">
        <div class="table-responsive">
            <table class="table table-bordered table-hover align-middle">
                <thead class="table-dark">
                    <tr>
                        <th>ID</th>
                        <th>Клієнт</th>
                        <th>Телефон</th>
                        <th>Дата продажу</th>
                        <th>Дата прийому</th>
                        <th>Дата видачі</th>
                        <th>Товар</th>
                        <th>Серійний №</th>
                        <th>Комплектація</th>
                        <th>Несправність</th>
                        <th>Статус</th>
                        <th>Дії</th>
                    </tr>
                </thead>
                <tbody id="ordersTable"></tbody>
            </table>
        </div>
    </div>

    <!-- Модальне вікно кошика -->
    <div class="modal fade" id="trashModal" tabindex="-1">
        <div class="modal-dialog modal-xl">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">🗑️ Кошик видалених замовлень</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <table class="table table-bordered">
                        <thead><tr><th>ID</th><th>Клієнт</th><th>Товар</th><th>Дата видалення</th><th>Дії</th></tr></thead>
                        <tbody id="trashTable"></tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <!-- Модальне вікно фото -->
    <div class="modal fade" id="photoModal" tabindex="-1">
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header"><h5 class="modal-title">🖼️ Фотографії замовлення</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
                <div class="modal-body">
                    <input type="file" id="photoFile" class="form-control mb-2" multiple>
                    <button class="btn btn-success btn-sm mb-3" onclick="uploadPhoto()">Завантажити фото</button>
                    <div id="photosContainer" class="d-flex flex-wrap gap-2"></div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        let currentPhotoOrderId = null;
        document.getElementById('date_in').valueAsDate = new Date();

        function loadOrders() {
            let search = document.getElementById('search').value;
            fetch('/api/orders?search=' + encodeURIComponent(search))
                .then(res => res.json())
                .then(data => {
                    let tbody = document.getElementById('ordersTable');
                    tbody.innerHTML = '';
                    data.forEach(o => {
                        let tr = document.createElement('tr');
                        let bg = '';
                        if (o.status === 'Готово') bg = 'background-color: #FFF2CC;';
                        else if (o.status === 'Видано') bg = 'background-color: #D6EAF8;';
                        else if (o.status === 'Повторний ремонт') bg = 'background-color: #FCE4D6;';
                        tr.style = bg;

                        tr.innerHTML = `
                            <td><b>#${o.id}</b></td>
                            <td contenteditable="true" onblur="updateCell(${o.id}, 'client_name', this.innerText)">${o.client_name || ''}</td>
                            <td contenteditable="true" onblur="updateCell(${o.id}, 'phone', this.innerText)">${o.phone || ''}</td>
                            <td contenteditable="true" onblur="updateCell(${o.id}, 'date_sale', this.innerText)">${o.date_sale || ''}</td>
                            <td contenteditable="true" onblur="updateCell(${o.id}, 'date_in', this.innerText)">${o.date_in || ''}</td>
                            <td contenteditable="true" onblur="updateCell(${o.id}, 'date_out', this.innerText)">${o.date_out || ''}</td>
                            <td contenteditable="true" onblur="updateCell(${o.id}, 'item_name', this.innerText)">${o.item_name || ''}</td>
                            <td contenteditable="true" onblur="updateCell(${o.id}, 'serial_num', this.innerText)">${o.serial_num || ''}</td>
                            <td contenteditable="true" onblur="updateCell(${o.id}, 'equipment', this.innerText)">${o.equipment || ''}</td>
                            <td contenteditable="true" onblur="updateCell(${o.id}, 'issue', this.innerText)">${o.issue || ''}</td>
                            <td>
                                <select class="form-select form-select-sm" onchange="updateStatus(${o.id}, this.value)">
                                    ${['В роботі', 'Очікує запчастин', 'Готово', 'Видано', 'Повторний ремонт'].map(s => `<option ${o.status === s ? 'selected' : ''}>${s}</option>`).join('')}
                                </select>
                            </td>
                            <td>
                                <button class="btn btn-info btn-sm mb-1" onclick="openPhotos(${o.id})">📷 Фото</button>
                                <a href="/print/${o.id}" target="_blank" class="btn btn-success btn-sm mb-1">🖨️ А5</a>
                                <button class="btn btn-danger btn-sm mb-1" onclick="deleteOrder(${o.id})">🗑️</button>
                            </td>
                        `;
                        tbody.appendChild(tr);
                    });
                });
        }

        function saveOrder() {
            let data = {
                client_name: document.getElementById('client_name').value,
                phone: document.getElementById('phone').value,
                item_name: document.getElementById('item_name').value,
                serial_num: document.getElementById('serial_num').value,
                equipment: document.getElementById('equipment').value,
                issue: document.getElementById('issue').value,
                status: document.getElementById('status').value,
                date_in: document.getElementById('date_in').value
            };
            fetch('/api/orders', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)})
                .then(() => { loadOrders(); document.getElementById('client_name').value=''; document.getElementById('item_name').value=''; });
        }

        function quickOrder() {
            fetch('/api/orders/quick', {method: 'POST'}).then(() => loadOrders());
        }

        function updateCell(id, field, value) {
            fetch(`/api/orders/${id}`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({field, value})});
        }

        function updateStatus(id, status) {
            fetch(`/api/orders/${id}/status`, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({status})})
                .then(() => loadOrders());
        }

        function deleteOrder(id) {
            if(confirm('Перенести замовлення в кошик?')) {
                fetch(`/api/orders/${id}`, {method: 'DELETE'}).then(() => loadOrders());
            }
        }

        function openPhotos(id) {
            currentPhotoOrderId = id;
            let modal = new bootstrap.Modal(document.getElementById('photoModal'));
            modal.show();
            loadPhotos();
        }

        function loadPhotos() {
            fetch(`/api/orders/${currentPhotoOrderId}/photos`)
                .then(res => res.json())
                .then(photos => {
                    let container = document.getElementById('photosContainer');
                    container.innerHTML = '';
                    photos.forEach(p => {
                        container.innerHTML += `<div><img src="/${p.path}" height="100" class="border rounded mb-1"><br><button class="btn btn-danger btn-sm w-100" onclick="deletePhoto(${p.id})">Видалити</button></div>`;
                    });
                });
        }

        function uploadPhoto() {
            let files = document.getElementById('photoFile').files;
            let formData = new FormData();
            for(let f of files) formData.append('photos', f);
            fetch(`/api/orders/${currentPhotoOrderId}/photos`, {method: 'POST', body: formData}).then(() => loadPhotos());
        }

        function deletePhoto(id) {
            fetch(`/api/photos/${id}`, {method: 'DELETE'}).then(() => loadPhotos());
        }

        function openTrash() {
            let modal = new bootstrap.Modal(document.getElementById('trashModal'));
            modal.show();
            fetch('/api/trash').then(res => res.json()).then(data => {
                let tbody = document.getElementById('trashTable');
                tbody.innerHTML = '';
                data.forEach(t => {
                    tbody.innerHTML += `<tr><td>#${t.original_id}</td><td>${t.client_name}</td><td>${t.item_name}</td><td>${t.deleted_at}</td><td><button class="btn btn-success btn-sm" onclick="restoreOrder(${t.original_id})">Відновити</button></td></tr>`;
                });
            });
        }

        function restoreOrder(id) {
            fetch(`/api/trash/${id}/restore`, {method: 'POST'}).then(() => { openTrash(); loadOrders(); });
        }

        loadOrders();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/orders', methods=['GET', 'POST'])
def handle_orders():
    conn = get_db()
    cursor = conn.cursor()
    if request.method == 'GET':
        search = request.args.get('search', '')
        if search:
            p = f"%{search}%"
            cursor.execute("SELECT * FROM orders WHERE client_name LIKE ? OR phone LIKE ? OR item_name LIKE ? OR serial_num LIKE ? ORDER BY id DESC", (p, p, p, p))
        else:
            cursor.execute("SELECT * FROM orders ORDER BY id DESC")
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return jsonify(rows)
    
    elif request.method == 'POST':
        data = request.json
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("""
            INSERT INTO orders (client_name, phone, date_in, date_out, item_name, serial_num, equipment, issue, status, date_sale)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('client_name', ''), data.get('phone', ''), data.get('date_in', today),
            data.get('date_out', ''), data.get('item_name', ''), data.get('serial_num', ''),
            data.get('equipment', ''), data.get('issue', ''), data.get('status', 'В роботі'), ''
        ))
        conn.commit()
        conn.close()
        return jsonify({"success": True})

@app.route('/api/orders/quick', methods=['POST'])
def quick_order():
    conn = get_db()
    cursor = conn.cursor()
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute("""
        INSERT INTO orders (client_name, phone, date_in, date_out, item_name, serial_num, equipment, issue, status)
        VALUES ('', '', ?, '', '', '', '', '', 'В роботі')
    """, (today,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/orders/<int:id>', methods=['PUT', 'DELETE'])
def modify_order(id):
    conn = get_db()
    cursor = conn.cursor()
    if request.method == 'PUT':
        data = request.json
        field = data.get('field')
        value = data.get('value')
        allowed_fields = ['client_name', 'phone', 'date_sale', 'date_in', 'date_out', 'item_name', 'serial_num', 'equipment', 'issue']
        if field in allowed_fields:
            cursor.execute(f"UPDATE orders SET {field} = ? WHERE id = ?", (value, id))
            conn.commit()
        conn.close()
        return jsonify({"success": True})
    
    elif request.method == 'DELETE':
        cursor.execute("SELECT * FROM orders WHERE id = ?", (id,))
        row = cursor.fetchone()
        if row:
            deleted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute("""
                INSERT INTO deleted_orders (original_id, client_name, phone, date_in, date_out, item_name, serial_num, equipment, issue, status, date_sale, deleted_at, first_date_in)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (row['id'], row['client_name'], row['phone'], row['date_in'], row['date_out'], row['item_name'], row['serial_num'], row['equipment'], row['issue'], row['status'], row['date_sale'], deleted_at, row['first_date_in']))
            cursor.execute("DELETE FROM orders WHERE id = ?", (id,))
            conn.commit()
        conn.close()
        return jsonify({"success": True})

@app.route('/api/orders/<int:id>/status', methods=['PUT'])
def update_status(id):
    data = request.json
    new_status = data.get('status')
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_db()
    cursor = conn.cursor()

    if new_status == "Повторний ремонт":
        cursor.execute("SELECT date_in, first_date_in FROM orders WHERE id = ?", (id,))
        row = cursor.fetchone()
        if row:
            first_in = row['first_date_in'] if row['first_date_in'] else row['date_in']
            cursor.execute("UPDATE orders SET status = ?, first_date_in = ?, date_in = ? WHERE id = ?", (new_status, first_in, today, id))
    elif new_status == "Видано":
        cursor.execute("UPDATE orders SET status = ?, date_out = ? WHERE id = ?", (new_status, today, id))
    else:
        cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (new_status, id))
    
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/orders/<int:id>/photos', methods=['GET', 'POST'])
def handle_photos(id):
    conn = get_db()
    cursor = conn.cursor()
    if request.method == 'GET':
        cursor.execute("SELECT id, photo_path FROM order_photos WHERE order_id = ?", (id,))
        photos = [{"id": r['id'], "path": os.path.relpath(r['photo_path'], BASE_DIR).replace('\\', '/')} for r in cursor.fetchall()]
        conn.close()
        return jsonify(photos)
    elif request.method == 'POST':
        files = request.files.getlist('photos')
        for f in files:
            if f:
                ext = os.path.splitext(f.filename)[1] or '.png'
                new_filename = f"order_{id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{ext}"
                dest_path = os.path.join(UPLOAD_DIR, new_filename)
                f.save(dest_path)
                cursor.execute("INSERT INTO order_photos (order_id, photo_path) VALUES (?, ?)", (id, dest_path))
        conn.commit()
        conn.close()
        return jsonify({"success": True})

@app.route('/api/photos/<int:photo_id>', methods=['DELETE'])
def delete_photo(photo_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT photo_path FROM order_photos WHERE id = ?", (photo_id,))
    row = cursor.fetchone()
    if row:
        path = row['photo_path']
        if os.path.exists(path):
            os.remove(path)
        cursor.execute("DELETE FROM order_photos WHERE id = ?", (photo_id,))
        conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/api/trash', methods=['GET'])
def get_trash():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM deleted_orders ORDER BY id DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(rows)

@app.route('/api/trash/<int:orig_id>/restore', methods=['POST'])
def restore_order(orig_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM deleted_orders WHERE original_id = ?", (orig_id,))
    row = cursor.fetchone()
    if row:
        cursor.execute("""
            INSERT INTO orders (id, client_name, phone, date_in, date_out, item_name, serial_num, equipment, issue, status, date_sale, first_date_in)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (row['original_id'], row['client_name'], row['phone'], row['date_in'], row['date_out'], row['item_name'], row['serial_num'], row['equipment'], row['issue'], row['status'], row['date_sale'], row['first_date_in']))
        cursor.execute("DELETE FROM deleted_orders WHERE original_id = ?", (orig_id,))
        conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route('/print/<int:id>')
def print_receipt(id):
    pdf_path = generate_pdf_receipt(id)
    if pdf_path and os.path.exists(pdf_path):
        return send_file(pdf_path, as_attachment=True)
    return "Помилка генерації квитанції", 404

# Статические файлы для загруженных фото
@app.route('/ServiceManagerData/uploads/<path:filename>')
def uploaded_file(filename):
    return send_file(os.path.join(UPLOAD_DIR, filename))

if __name__ == '__main__':
    print("Сервер запущен! Откройте в браузере: http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
