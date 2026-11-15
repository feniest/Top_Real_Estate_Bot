import base64
import ctypes
import sys
import os
import time
import urllib.request
import urllib.parse
import json
import logging
import tempfile
import shutil
import psycopg2
import bcrypt
from io import BytesIO
from datetime import datetime, date
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QLineEdit, QPushButton, 
    QVBoxLayout, QHBoxLayout, QTabWidget, QTableWidget, 
    QTableWidgetItem, QCheckBox, QMessageBox, QFileDialog, 
    QDialog, QHeaderView, QTextEdit, QComboBox, QStackedWidget,
    QProgressBar
)
from PyQt6.QtGui import QIcon, QPixmap, QImage
from PyQt6.QtCore import Qt, QSize, QTimer, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget

# Настройка логирования
base_dir = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
log_path = os.path.join(base_dir, 'actions.log')
last_sent_flag_path = os.path.join(base_dir, '.last_telegram_log_sent')

logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

# === НАСТРОЙКИ TELEGRAM ===
TELEGRAM_BOT_TOKEN = "ВАШ_ТОКЕН_БОТА"  
TELEGRAM_CHAT_ID = "ВАШ_CHAT_ID"        

def send_log_to_telegram():
    """Автоматическая отправка лог-файла разработчику в Telegram не чаще одного раза в сутки"""
    today_str = date.today().isoformat()
    
    if os.path.exists(last_sent_flag_path):
        try:
            with open(last_sent_flag_path, "r", encoding="utf-8") as f:
                last_date = f.read().strip()
                if last_date == today_str:
                    return
        except Exception:
            pass

    if not os.path.exists(log_path):
        return

    if TELEGRAM_BOT_TOKEN == "ВАШ_ТОКЕН_БОТА" or TELEGRAM_CHAT_ID == "ВАШ_CHAT_ID":
        return

    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        
        with open(log_path, "rb") as f:
            file_bytes = f.read()

        boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
        body_parts = []
        
        body_parts.append(f'--{boundary}\r\n'.encode('utf-8'))
        body_parts.append(b'Content-Disposition: form-data; name="chat_id"\r\n\r\n')
        body_parts.append(str(TELEGRAM_CHAT_ID).encode('utf-8') + b'\r\n')
        
        caption_text = f'📊 Автоматический отчет логов РБД Управление недвижимостью ({today_str})'
        body_parts.append(f'--{boundary}\r\n'.encode('utf-8'))
        body_parts.append(b'Content-Disposition: form-data; name="caption"\r\n\r\n')
        body_parts.append(caption_text.encode('utf-8') + b'\r\n')
        
        body_parts.append(f'--{boundary}\r\n'.encode('utf-8'))
        body_parts.append(b'Content-Disposition: form-data; name="document"; filename="actions.log"\r\n')
        body_parts.append(b'Content-Type: text/plain\r\n\r\n')
        body_parts.append(file_bytes + b'\r\n')
        
        body_parts.append(f'--{boundary}--\r\n'.encode('utf-8'))
        body = b''.join(body_parts)
        
        req = urllib.request.Request(url, data=body)
        req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
        
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            if res_data.get("ok"):
                with open(last_sent_flag_path, "w", encoding="utf-8") as f:
                    f.write(today_str)
                logging.info("Системный журнал (actions.log) успешно отправлен разработчику в Telegram.")
            else:
                logging.error(f"Telegram API вернул ошибку при отправке логов: {res_data}")
    except Exception as e:
        logging.error(f"Не удалось отправить лог-файл в Telegram разработчику: {e}")

def get_db_connection():
    """Подключение к удаленной базе данных PostgreSQL"""
    try:
        conn = psycopg2.connect(
            host="37.187.139.87",
            port=35919,
            database="fh7cba1949de20442fb8484660cc696208",
            user="postgres",
            password="7H6SEUopuXHTa9Hu9vpJ04onLYZ4",
            connect_timeout=5
        )
        return conn
    except Exception as e:
        print(f"КРИТИЧЕСКАЯ ОШИБКА БД: {e}")
        logging.error(f"Критическая ошибка БД (хост: 37.187.139.87): {e}")
        raise e 

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(stored_password, provided_password):
    try:
        return bcrypt.checkpw(provided_password.encode('utf-8'), stored_password.encode('utf-8'))
    except Exception:
        return stored_password == provided_password

class ProgressDialog(QDialog):
    def __init__(self, title, message, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Статус")
        self.setFixedSize(620, 140)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint | Qt.WindowType.WindowTitleHint)
        self.setModal(True)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(10)
        
        self.label = QLabel(f"   {message}")
        self.label.setStyleSheet("font-size: 13px; font-weight: 600; color: #1f2937;")
        self.label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.label)
        
        self.speed_label = QLabel("   Скорость: 0.0 МБ/с")
        self.speed_label.setStyleSheet("font-size: 12px; color: #4b5563; font-weight: 500;")
        self.speed_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.speed_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #d1d5db;
                border-radius: 8px;
                background-color: #f3f4f6;
            }
            QProgressBar::chunk {
                background-color: #2563eb;
                border-radius: 8px;
            }
        """)
        layout.addWidget(self.progress_bar)
        self.setLayout(layout)

def init_db(parent=None):
    dlg = ProgressDialog("Подготовка", "Подождите, идёт подготовка базы данных...", parent)
    dlg.show()
    QApplication.processEvents()
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ads (
                id SERIAL PRIMARY KEY,
                ad_number VARCHAR(50) UNIQUE NOT NULL,
                category VARCHAR(50) NOT NULL,
                property_type VARCHAR(50) NOT NULL,
                rooms VARCHAR(20) NOT NULL,
                district TEXT NOT NULL,
                landmark TEXT NOT NULL,
                area REAL,
                floor INTEGER,
                floors_total INTEGER NOT NULL,
                price REAL NOT NULL,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS archive_ads (
                id SERIAL PRIMARY KEY,
                ad_number VARCHAR(50) UNIQUE NOT NULL,
                category VARCHAR(50) NOT NULL,
                property_type VARCHAR(50) NOT NULL,
                rooms VARCHAR(20) NOT NULL,
                district TEXT NOT NULL,
                landmark TEXT NOT NULL,
                area REAL,
                floor INTEGER,
                floors_total INTEGER NOT NULL,
                price REAL NOT NULL,
                deleted_at TEXT NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ad_media (
                id SERIAL PRIMARY KEY,
                ad_number VARCHAR(50) NOT NULL,
                file_name TEXT NOT NULL,
                file_data BYTEA NOT NULL
            )
        ''')
        
        cursor.execute('''
            ALTER TABLE ad_media ADD COLUMN IF NOT EXISTS ad_number VARCHAR(50);
        ''')
        
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] == 0:
            p_admin = hash_password("admin123")
            p_op = hash_password("op123")
            cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", ("admin", p_admin, "admin"))
            cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", ("operator", p_op, "operator"))
            
        conn.commit()
        cursor.close()
        conn.close()
        logging.info("Подготовка и инициализация структуры PostgreSQL (хост: 37.187.139.87) выполнены успешно.")
    except Exception as e:
        logging.critical(f"Ошибка подключения к PostgreSQL (хост: 37.187.139.87): {e}")
        print(f"Критическая ошибка подключения к БД: {e}")
        raise e
    finally:
        dlg.close()

class ImageViewerDialog(QDialog):
    def __init__(self, media_list, ad_num, parent=None):
        super().__init__(parent)
        self.media_list = media_list
        self.current_index = 0
        self.ad_num = ad_num
        
        self.setWindowTitle(f"Медиафайлы — Объявление № {self.ad_num}")
        self.resize(800, 600)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        
        self.stack = QStackedWidget()
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #111827; border-radius: 8px;")
        self.stack.addWidget(self.image_label)
        
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: #111827; border-radius: 8px;")
        self.media_player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.media_player.setAudioOutput(self.audio_output)
        self.media_player.setVideoOutput(self.video_widget)
        self.stack.addWidget(self.video_widget)
        
        layout.addWidget(self.stack, stretch=1)
        
        self.video_controls_layout = QHBoxLayout()
        self.btn_play_pause = QPushButton("▶️ Воспроизвести видео")
        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        self.video_controls_layout.addStretch()
        self.video_controls_layout.addWidget(self.btn_play_pause)
        self.video_controls_layout.addStretch()
        layout.addLayout(self.video_controls_layout)
        
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(10)
        
        self.btn_prev = QPushButton("⬅️ Назад")
        self.btn_next = QPushButton("Вперед ➡️")
        self.counter_label = QLabel()
        self.counter_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.counter_label.setStyleSheet("font-weight: bold; color: #374151; font-size: 14px;")
        
        self.btn_prev.clicked.connect(self.prev_media)
        self.btn_next.clicked.connect(self.next_media)
        
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.counter_label, stretch=1)
        nav_layout.addWidget(self.btn_next)
        
        layout.addLayout(nav_layout)
        self.setLayout(layout)
        self.update_media_view()

    def update_media_view(self):
        self.media_player.stop()
        if not self.media_list:
            return
            
        file_path, file_name = self.media_list[self.current_index]
        ext = file_name.lower().split('.')[-1]
        
        self.counter_label.setText(f"{file_name} ({self.current_index + 1} из {len(self.media_list)})")
        self.btn_prev.setEnabled(self.current_index > 0)
        self.btn_next.setEnabled(self.current_index < len(self.media_list) - 1)
        
        if ext in ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif']:
            self.stack.setCurrentIndex(0)
            self.set_video_controls_visible(False)
            image = QImage(file_path)
            if not image.isNull():
                pixmap = QPixmap.fromImage(image)
                self.image_label.setPixmap(pixmap.scaled(760, 480, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                self.image_label.setText("⚠️ Не удалось загрузить изображение")
        elif ext in ['mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv']:
            self.stack.setCurrentIndex(1)
            self.set_video_controls_visible(True)
            try:
                self.media_player.setSource(QUrl.fromLocalFile(file_path))
                self.btn_play_pause.setText("▶️ Воспроизвести видео")
            except Exception as e:
                logging.error(f"Ошибка инициализации видеоплеера: {e}")
        else:
            self.stack.setCurrentIndex(0)
            self.set_video_controls_visible(False)
            self.image_label.setText(f"📁 Файл: {file_name}\n(Предпросмотр недоступен)")

    def set_video_controls_visible(self, visible):
        for i in range(self.video_controls_layout.count()):
            w = self.video_controls_layout.itemAt(i).widget()
            if w:
                w.setVisible(visible)

    def toggle_play_pause(self):
        if self.media_player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.media_player.pause()
            self.btn_play_pause.setText("▶️ Воспроизвести видео")
        else:
            self.media_player.play()
            self.btn_play_pause.setText("⏸️ Пауза")

    def prev_media(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.update_media_view()

    def next_media(self):
        if self.current_index < len(self.media_list) - 1:
            self.current_index += 1
            self.update_media_view()

    def closeEvent(self, event):
        self.media_player.stop()
        event.accept()

class AuthWindow(QDialog):
    """Окно авторизации"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Авторизация")
        self.setFixedSize(320, 200)
        self.user_data = None
        
        if os.path.exists("app_icon.ico"):
            self.setWindowIcon(QIcon("app_icon.ico"))
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Логин")
        layout.addWidget(QLabel("Логин:"))
        layout.addWidget(self.username_input)
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Пароль")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(QLabel("Пароль:"))
        layout.addWidget(self.password_input)
        
        self.login_btn = QPushButton("Войти")
        self.login_btn.clicked.connect(self.handle_login)
        layout.addWidget(self.login_btn)
        
        self.setLayout(layout)

    def handle_login(self):
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT password, role FROM users WHERE username=%s", (username,))
            res = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if res and verify_password(res[0], password):
                self.user_data = {"username": username, "role": res[1]}
                logging.info(f"Пользователь '{username}' (роль: {res[1]}) успешно авторизован на хосте 37.187.139.87.")
                self.accept()
            else:
                logging.warning(f"Неудачная попытка входа для пользователя: '{username}' (хост: 37.187.139.87)")
                QMessageBox.warning(self, "Ошибка", "Неверный логин или пароль!")
        except Exception as e:
            logging.error(f"Ошибка при попытке авторизации (хост: 37.187.139.87): {e}")
            QMessageBox.critical(self, "Ошибка сети", f"Не удалось подключиться к базе данных: {e}")

class MainWindow(QMainWindow):
    """Основное окно программы"""
    def __init__(self, user_info):
        super().__init__()
        self.user_info = user_info
        self.switch_user_requested = False  # Флаг для горячей смены пользователя
        self.setWindowTitle(f"РБД Управление недвижимостью (PostgreSQL: 37.187.139.87) - Пользователь: {user_info['username']} ({user_info['role']})")
        self.resize(1360, 780)
        
        self.session_temp_dir = tempfile.mkdtemp(prefix="rbd_media_cache_")
        
        if os.path.exists("app_icon.ico"):
            self.setWindowIcon(QIcon("app_icon.ico"))
            
        self.init_ui()
        QTimer.singleShot(100, self.load_table_data)
        QTimer.singleShot(1200, send_log_to_telegram)

    def closeEvent(self, event):
        if self.switch_user_requested:
            try:
                if os.path.exists(self.session_temp_dir):
                    shutil.rmtree(self.session_temp_dir)
            except Exception:
                pass
            event.accept()
            return

        reply = QMessageBox.question(
            self, 
            "Подтверждение выхода", 
            "Вы действительно желаете завершить работу с программой? Если вы подтверждаете 'Выход', то все временные Медиа-файлы будут удалены.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if os.path.exists(self.session_temp_dir):
                    shutil.rmtree(self.session_temp_dir)
                    logging.info(f"Временная папка кэша медиафайлов успешно очищена перед выходом: {self.session_temp_dir}")
            except Exception as e:
                logging.error(f"Ошибка при очистке временной папки: {e}")
            event.accept()
        else:
            event.ignore()

    def init_ui(self):
        central_widget = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)
        
        # --- ПРАВАЯ ПАНЕЛЬ ИНСТРУМЕНТОВ (ToolBox) ---
        tools_layout = QVBoxLayout()
        tools_layout.setSpacing(8)
        
        lbl_panel = QLabel("<b>Панель ввода данных</b>")
        lbl_panel.setStyleSheet("font-size: 14px; color: #1f2937; margin-bottom: 5px;")
        tools_layout.addWidget(lbl_panel)
        
        self.inputs = {}
        fields = [
            ("Объяв-е №", "ad_number"),
            ("Район", "district"),
            ("Ориентир", "landmark"),
            ("Комн.", "rooms"),
            ("Этаж / Площадь", "floor_area"),
            ("Этажность", "floors_total"),
            ("Цена", "price")
        ]
        
        for label_text, key in fields:
            l = QLabel(label_text)
            l.setStyleSheet("color: #4b5563; font-weight: 600; font-size: 12px;")
            tools_layout.addWidget(l)
            line_edit = QLineEdit()
            line_edit.setEnabled(False)
            self.inputs[key] = line_edit
            tools_layout.addWidget(line_edit)
            
        tools_layout.addSpacing(10)
        
        self.btn_create = QPushButton("✨ Создать")
        self.btn_edit = QPushButton("✏️ Изменить")
        self.btn_save = QPushButton("💾 Сохранить")
        self.btn_media = QPushButton("📁 М-Файлы")
        self.btn_delete = QPushButton("🗑️ Удалить")
        self.btn_delete_multi = QPushButton("🗑️ Удалить несколько")
        
        for btn in [self.btn_create, self.btn_edit, self.btn_save, self.btn_media, self.btn_delete, self.btn_delete_multi]:
            tools_layout.addWidget(btn)
            
        tools_layout.addSpacing(10)
        
        # КНОПКА СМЕНЫ ПОЛЬЗОВАТЕЛЯ ДЛЯ ОПЕРАТОРА И АДМИНИСТРАТОРА
        self.btn_switch_user = QPushButton("🔄 Сменить пользователя")
        self.btn_switch_user.setStyleSheet("background-color: #eff6ff; color: #1e40af; font-weight: bold; border: 1px solid #bfdbfe;")
        self.btn_switch_user.clicked.connect(self.switch_user)
        tools_layout.addWidget(self.btn_switch_user)
            
        self.btn_create.clicked.connect(self.enable_creation)
        self.btn_edit.clicked.connect(self.enable_editing)
        self.btn_save.clicked.connect(self.save_data)
        self.btn_media.clicked.connect(self.upload_media)
        self.btn_delete.clicked.connect(self.delete_records)
        self.btn_delete_multi.clicked.connect(self.delete_multiple_records)
        
        tools_layout.addStretch()
        
        # --- ЛЕВАЯ ПАНЕЛЬ ОТОБРАЖЕНИЯ (Вкладки + Поиск) ---
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        lbl_search = QLabel("🔍 Быстрый поиск:")
        lbl_search.setStyleSheet("font-weight: bold; color: #374151;")
        search_layout.addWidget(lbl_search)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Введите район или ориентир для фильтрации...")
        self.search_input.textChanged.connect(self.filter_tables)
        search_layout.addWidget(self.search_input)
        left_layout.addLayout(search_layout)
        
        self.tabs_main = QTabWidget()
        self.tabs_main.currentChanged.connect(self.clear_all_checkboxes)
        
        self.tab_rent = QWidget()
        self.tab_sales = QWidget()
        
        self.tabs_main.addTab(self.tab_rent, "🔑 Аренда (Rent)")
        self.tabs_main.addTab(self.tab_sales, "📄 Продажа (Sales)")
        
        self.setup_category_tabs(self.tab_rent, "Rent")
        self.setup_category_tabs(self.tab_sales, "Sales")
        
        self.tab_help = QWidget()
        self.setup_help_tab(self.tab_help)
        self.tabs_main.addTab(self.tab_help, "📖 Помощь")
        
        if self.user_info['role'] == 'admin':
            self.tab_tools = QWidget()
            self.tabs_main.addTab(self.tab_tools, "⚙️ Инструменты (Tools)")
            self.setup_tools_tab(self.tab_tools)
            
        left_layout.addWidget(self.tabs_main)
        main_layout.addLayout(left_layout, stretch=4)
        
        tools_container = QWidget()
        tools_container.setLayout(tools_layout)
        tools_container.setFixedWidth(240)
        main_layout.addWidget(tools_container)
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f3f4f6;
            }
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
                color: #1f2937;
            }
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 6px 10px;
                selection-background-color: #2563eb;
            }
            QLineEdit:enabled:focus {
                border: 2px solid #2563eb;
            }
            QLineEdit:disabled {
                background-color: #e5e7eb;
                color: #9ca3af;
            }
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d1d5db;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: 600;
                color: #374151;
            }
            QPushButton:hover {
                background-color: #f8fafc;
                border-color: #9ca3af;
            }
            QPushButton:pressed {
                background-color: #e2e8f0;
            }
            QPushButton#btn_save {
                background-color: #2563eb;
                color: white;
                border: none;
            }
            QPushButton#btn_save:hover {
                background-color: #1d4ed8;
            }
            QTabWidget::pane {
                border: 1px solid #d1d5db;
                border-radius: 6px;
                background-color: #ffffff;
                margin: 0px;
                padding: 0px;
            }
            QTabWidget {
                margin: 0px;
                padding: 0px;
            }
            QTabBar::tab {
                background-color: #e5e7eb;
                color: #4b5563;
                padding: 7px 14px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                margin-right: 2px;
                font-weight: 600;
            }
            QTabBar::tab:selected {
                background-color: #2563eb;
                color: #ffffff;
            }
            QTabBar::tab:!selected:hover {
                background-color: #d1d5db;
            }
            QTableWidget {
                background-color: #ffffff;
                gridline-color: #e5e7eb;
                border: 1px solid #e5e7eb;
                border-radius: 4px;
                selection-background-color: #dbeafe;
                selection-color: #1e3a8a;
                margin: 0px;
            }
            QHeaderView::section {
                background-color: #f8fafc;
                color: #374151;
                padding: 8px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
                font-weight: 700;
            }
        """)

        self.btn_save.setObjectName("btn_save")
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)

    def setup_help_tab(self, parent_tab):
        """Метод инициализации вкладки 'Помощь' с полным описанием всех возможностей программы"""
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        
        help_text = QTextEdit()
        help_text.setReadOnly(True)
        help_text.setStyleSheet("background-color: #ffffff; border: 1px solid #d1d5db; border-radius: 6px; padding: 10px; font-size: 13px; color: #1f2937;")
        
        html_content = """
        <h2 style='color: #2563eb;'>📖 Полное руководство пользователя: «РБД Управление недвижимостью»</h2>
        
        <p>Настольное приложение <b>«РБД Управление недвижимостью»</b> предназначено для подготовки оператором информации об объектах недвижимости (аренда и продажа), хранения мультимедийных материалов в удаленной базе данных PostgreSQL и дальнейшей работы "TopRealEstateBot" в Telegram.</p>
        
        <h3>1. Структура интерфейса и навигация</h3>
        <ul>
            <li><b>Категории сделок:</b> Главные вкладки программы разделяют объекты на <b>«Аренда (Rent)»</b> и <b>«Продажа (Sales)»</b>.</li>
            <li><b>Типы недвижимости:</b> Внутри каждой категории подразделами выступают <b>«Квартиры (Apartments)»</b> и <b>«Дома (Houses)»</b>.</li>
            <li><b>Комнатность:</b> Объекты распределены по вкладкам от <b>1-комн.</b> до <b>5-комн.</b></li>
            <li><b>Строка быстрого поиска:</b> Расположена в верхней части слева. Позволяет мгновенно находить и фильтровать объекты в таблицах в режиме реального времени по введенному району или ориентиру (поддерживает несколько ключевых слов через пробел).</li>
        </ul>
        
        <h3>2. Управление данными (Панель ввода справа)</h3>
        <ul>
            <li><b>✨ Создать:</b> Разблокирует поля ввода для добавления нового объекта. После заполнения полей нажмите <b>«Сохранить»</b>. <i>Подсказка:</i> поддерживается быстрая вставка скопированных строк из буфера обмена с помощью комбинации клавиш `Ctrl + V`.</li>
            <li><b>✏️ Изменить:</b> Позволяет отредактировать существующий объект. Отметьте нужную строку галочкой (`CheckBox`) в таблице, нажмите <b>«Изменить»</b>, внесите корректировки в панели справа и сохраните результат. Одновременно можно редактировать только одну запись.</li>
            <li><b>💾 Сохранить:</b> Фиксирует добавленные или измененные данные в удаленной базе данных PostgreSQL (хост: `37.187.139.87`). Процесс сопровождается статус-баром.</li>
            <li><b>📁 М-Файлы (Прикрепление медиа):</b> Позволяет загрузить фотографии и видео к выбранному объекту. 
                <ul>
                    <li><b>Жесткий лимит:</b> Суммарный размер прикрепляемых за раз файлов не должен превышать <b>50 МБ</b>. При превышении программа выдает ошибку и блокирует отправку.</li>
                    <li>Конвертация или сжатие файлов не производятся, файлы сохраняются в исходном качестве в бинарном формате (`BYTEA`) в базе данных.</li>
                </ul>
            </li>
            <li><b>🖼️ Встроенный Медиа-просмотрщик:</b> Чтобы просмотреть фото или видео, дважды кликните (`Double Click`) по ячейке в колонке <b>«Медиа»</b> нужного объекта в таблице. В открывшемся окне можно листать файлы кнопками «Назад» / «Вперед» и управлять воспроизведением видео.</li>
            <li><b>🗑️ Удалить / Удалить несколько:</b> Переносит выбранные объекты в архив (`archive_ads`) с фиксацией даты и времени удаления, после чего скрывает их из активных таблиц.</li>
            <li><b>🔄 Сменить пользователя:</b> Кнопка быстрого доступа позволяет завершить текущий сеанс и вернуться к окну авторизации без перезапуска самого приложения.</li>
        </ul>
        
        <h3>3. Инструменты администратора (Вкладка «Tools»)</h3>
        <p>Доступна только пользователям с ролью <b>admin</b>:</p>
        <ul>
            <li><b>📋 Системный журнал (`actions.log`):</b> Просмотр всех действий пользователей и системных ошибок.</li>
            <li><b>🔄 Управление архивом:</b> Просмотр удаленных объектов и их последующее восстановление обратно в активную базу данных.</li>
            <li><b>👥 Управление операторами:</b> Добавление новых учетных записей сотрудников и удаление существующих.</li>
        </ul>
        
        <h3>💡 Полезные советы и особенности:</h3>
        <ol>
            <li>При переключении между любыми вкладками таблиц все ранее проставленные галочки автоматически сбрасываются для предотвращения случайных массовых операций.</li>
            <li>Числовые поля (этаж, этажность, цена) проверяются на корректность ввода.</li>
            <li>Все скачанные из базы медиафайлы кэшируются во временной системной папке сеанса (`rbd_media_cache_*`) и полностью удаляются с компьютера при закрытии программы.</li>
        </ol>

        <hr style='border: 1px solid #e5e7eb; margin: 20px 0;'>
        <p><b>Разработчик программы:</b> Кинзябаев Ринат Наильевич<br>
        <b>E-mail:</b> feniest@gmail.com<br>
        <b>Тел.:</b> +998(95) 151-6496<br>
        <b>Версия программы:</b> 3.16</p>
        """
        
        help_text.setHtml(html_content)
        layout.addWidget(help_text)
        parent_tab.setLayout(layout)

    def apply_column_widths(self, table, prop_type="Apartments"):
        table.setColumnWidth(0, 110)
        table.setColumnWidth(1, 145)
        table.setColumnWidth(2, 145)
        table.setColumnWidth(3, 65)
        if prop_type == "Houses":
            table.setColumnWidth(4, 100)
        else:
            table.setColumnWidth(4, 90)
        table.setColumnWidth(5, 95)
        table.setColumnWidth(6, 110)
        table.setColumnWidth(7, 180)
        table.setColumnWidth(8, 60)

    def clear_all_checkboxes(self):
        rooms_list = ["1-room", "2-room", "3-room", "4-room", "5-room"]
        categories = [("Rent", "Apartments"), ("Rent", "Houses"), ("Sales", "Apartments"), ("Sales", "Houses")]
        for cat, pt in categories:
            for r in rooms_list:
                tbl = getattr(self, f"table_{cat}_{pt}_{r}", None)
                if tbl:
                    for row in range(tbl.rowCount()):
                        chk = tbl.cellWidget(row, 8)
                        if chk and chk.isChecked():
                            chk.blockSignals(True)
                            chk.setChecked(False)
                            chk.blockSignals(False)

    def filter_tables(self):
        query = self.search_input.text().strip().lower()
        query_terms = query.split() if query else []
        rooms_list = ["1-room", "2-room", "3-room", "4-room", "5-room"]
        categories = [("Rent", "Apartments"), ("Rent", "Houses"), ("Sales", "Apartments"), ("Sales", "Houses")]
        
        for cat, pt in categories:
            for r in rooms_list:
                tbl = getattr(self, f"table_{cat}_{pt}_{r}", None)
                if tbl:
                    for row in range(tbl.rowCount()):
                        if not query_terms:
                            tbl.setRowHidden(row, False)
                            continue
                        district_item = tbl.item(row, 1)
                        landmark_item = tbl.item(row, 2)
                        target_text = ""
                        if district_item:
                            target_text += " " + district_item.text().lower()
                        if landmark_item:
                            target_text += " " + landmark_item.text().lower()
                        match = all(term in target_text for term in query_terms)
                        tbl.setRowHidden(row, not match)

    def setup_tools_tab(self, parent_tab):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        
        layout.addWidget(QLabel("<b>Панель расширенного администрирования</b>"))
        
        btn_logs = QPushButton("📋 Просмотреть системный журнал (actions.log)")
        btn_logs.clicked.connect(self.view_system_logs)
        layout.addWidget(btn_logs)
        
        btn_backup = QPushButton("💾 Резервная копия базы данных")
        btn_backup.clicked.connect(lambda: QMessageBox.information(self, "Бэкап", "Резервные копии базы данных создаются на сервере."))
        layout.addWidget(btn_backup)
        
        btn_clear_db = QPushButton("⚠️ Полная очистка базы данных (Сброс всех объявлений)")
        btn_clear_db.setStyleSheet("background-color: #fee2e2; color: #990000; font-weight: bold; border: 1px solid #f87171;")
        btn_clear_db.clicked.connect(self.clear_entire_database)
        layout.addWidget(btn_clear_db)
        
        btn_restore = QPushButton("🔄 Управление архивом (Восстановление записей из АБД)")
        btn_restore.clicked.connect(self.open_restore_dialog)
        layout.addWidget(btn_restore)
        
        layout.addWidget(QLabel("<br><b>👥 Управление учетными записями операторов</b>"))
        
        self.users_table = QTableWidget()
        self.load_users_table()
        layout.addWidget(self.users_table)
        
        user_btn_layout = QHBoxLayout()
        user_btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_add_user = QPushButton("➕ Добавить оператора")
        btn_add_user.clicked.connect(self.add_user_dialog)
        btn_del_user = QPushButton("✖️ Удалить выбранного")
        btn_del_user.clicked.connect(self.delete_user)
        
        user_btn_layout.addWidget(btn_add_user)
        user_btn_layout.addWidget(btn_del_user)
        layout.addLayout(user_btn_layout)
        parent_tab.setLayout(layout)

    def switch_user(self):
        """Метод для горячей смены пользователя без перезапуска процесса программы"""
        reply = QMessageBox.question(
            self, "Смена пользователя", 
            "Вы действительно хотите завершить текущий сеанс и войти под другой учетной записью?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            logging.info(f"Пользователь {self.user_info['username']} инициировал горячую смену пользователя.")
            self.switch_user_requested = True
            
            try:
                if os.path.exists(self.session_temp_dir):
                    shutil.rmtree(self.session_temp_dir)
            except Exception:
                pass
            
            self.close()
            
            global auth_global, window_global
            auth_global = AuthWindow()
            if auth_global.exec() == QDialog.DialogCode.Accepted and auth_global.user_data:
                window_global = MainWindow(auth_global.user_data)
                window_global.show()

    def clear_entire_database(self):
        reply = QMessageBox.question(
            self, "Внимание: Очистка базы", 
            "Вы уверены, что хотите полностью удалить ВСЕ объявления и архивные записи?\nЭто действие необратимо!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            dlg = ProgressDialog("Обновление", "Подождите, идёт обновление базы данных...", self)
            dlg.show()
            QApplication.processEvents()
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("TRUNCATE TABLE ads, archive_ads, ad_media RESTART IDENTITY CASCADE;")
                conn.commit()
                cursor.close()
                conn.close()
                dlg.close()
                logging.warning(f"Администратор {self.user_info['username']} произвел ПОЛНУЮ ОЧИСТКУ базы данных на хосте 37.187.139.87!")
                QMessageBox.information(self, "Успех", "База данных успешно очищена!")
                self.load_table_data()
            except Exception as e:
                dlg.close()
                logging.error(f"Ошибка при полной очистке базы (хост: 37.187.139.87): {e}")
                QMessageBox.critical(self, "Ошибка", f"Не удалось очистить базу: {e}")

    def view_system_logs(self):
        logging.info(f"Администратор {self.user_info['username']} открыл системный журнал (хост: 37.187.139.87).")
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8") as f:
                content = f.read()
            dlg = QDialog(self)
            dlg.setWindowTitle("actions.log")
            dlg.resize(850, 550)
            lay = QVBoxLayout()
            te = QTextEdit()
            te.setPlainText(content)
            te.setReadOnly(True)
            lay.addWidget(te)
            dlg.setLayout(lay)
            dlg.exec()
        else:
            QMessageBox.information(self, "Логи", "actions.log пуст.")

    def load_users_table(self):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, role FROM users")
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            
            self.users_table.setColumnCount(4)
            self.users_table.setHorizontalHeaderLabels(["ID", "Логин", "Роль", "Выбор"])
            self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            self.users_table.setRowCount(len(rows))
            for row_idx, row_data in enumerate(rows):
                for col_idx, val in enumerate(row_data):
                    self.users_table.setItem(row_idx, col_idx, QTableWidgetItem(str(val)))
                self.users_table.setCellWidget(row_idx, 3, QCheckBox())
        except Exception as e:
            logging.error(f"Ошибка загрузки пользователей (хост: 37.187.139.87): {e}")

    def add_user_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Добавить оператора")
        dlg.setFixedSize(320, 220)
        lay = QVBoxLayout()
        lay.setContentsMargins(20, 20, 20, 20)
        lay.setSpacing(10)
        
        u_in = QLineEdit()
        u_in.setPlaceholderText("Логин")
        p_in = QLineEdit()
        p_in.setPlaceholderText("Пароль")
        p_in.setEchoMode(QLineEdit.EchoMode.Password)
        r_co = QComboBox()
        r_co.addItems(["operator", "admin"])
        
        lay.addWidget(QLabel("Логин:"))
        lay.addWidget(u_in)
        lay.addWidget(QLabel("Пароль:"))
        lay.addWidget(p_in)
        lay.addWidget(QLabel("Роль:"))
        lay.addWidget(r_co)
        
        btn_save = QPushButton("Создать")
        def save():
            uname, upass, urole = u_in.text().strip(), p_in.text().strip(), r_co.currentText()
            if not uname or not upass:
                QMessageBox.warning(dlg, "Ошибка", "Заполните все поля!")
                return
            prog_dlg = ProgressDialog("Обновление", "Подождите, идёт обновление базы данных...", dlg)
            prog_dlg.show()
            QApplication.processEvents()
            try:
                hashed_pw = hash_password(upass)
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", (uname, hashed_pw, urole))
                conn.commit()
                cursor.close()
                conn.close()
                prog_dlg.close()
                logging.info(f"Администратор {self.user_info['username']} добавил пользователя '{uname}' с ролью '{urole}' (хост: 37.187.139.87).")
                QMessageBox.information(dlg, "Успех", f"Пользователь '{uname}' добавлен!")
                dlg.accept()
                self.load_users_table()
            except Exception as e:
                prog_dlg.close()
                logging.error(f"Ошибка при добавлении пользователя (хост: 37.187.139.87): {e}")
                QMessageBox.critical(dlg, "Ошибка", f"Не удалось добавить: {e}")
        btn_save.clicked.connect(save)
        lay.addWidget(btn_save)
        dlg.setLayout(lay)
        dlg.exec()

    def delete_user(self):
        target = None
        for row in range(self.users_table.rowCount()):
            chk = self.users_table.cellWidget(row, 3)
            if chk and chk.isChecked():
                target = (self.users_table.item(row, 0).text(), self.users_table.item(row, 1).text())
                break
        if not target:
            QMessageBox.warning(self, "Ошибка", "Выберите пользователя!")
            return
        uid, uname = target
        if uname == "admin":
            QMessageBox.warning(self, "Ошибка", "Нельзя удалить главного администратора!")
            return
        if QMessageBox.question(self, "Удаление", f"Удалить '{uname}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            dlg_status = ProgressDialog("Обновление", "Подождите, идёт обновление базы данных...", self)
            dlg_status.show()
            QApplication.processEvents()
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE id=%s", (uid,))
                conn.commit()
                cursor.close()
                conn.close()
                dlg_status.close()
                logging.info(f"Администратор {self.user_info['username']} удалил пользователя '{uname}' (хост: 37.187.139.87).")
                self.load_users_table()
            except Exception as e:
                dlg_status.close()
                logging.error(f"Ошибка при удалении пользователя (хост: 37.187.139.87): {e}")
                QMessageBox.critical(dlg, "Ошибка", f"{e}")

    def open_restore_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Восстановление из АБД")
        dlg.resize(950, 480)
        lay = QVBoxLayout()
        lay.setContentsMargins(15, 15, 15, 15)
        
        table = QTableWidget()
        table.setColumnCount(8)
        table.setHorizontalHeaderLabels(["Объяв-е №", "Категория", "Тип", "Комн.", "Район", "Цена", "Дата удаления", "Выбор"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT ad_number, category, property_type, rooms, district, price, deleted_at FROM archive_ads")
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
        except Exception:
            rows = []
            
        table.setRowCount(len(rows))
        for r_idx, r_dat in enumerate(rows):
            for c_idx, val in enumerate(r_dat):
                table.setItem(r_idx, c_idx, QTableWidgetItem(str(val)))
            table.setCellWidget(r_idx, 7, QCheckBox())
        lay.addWidget(table)
        
        def restore():
            sel = None
            for r in range(table.rowCount()):
                chk = table.cellWidget(r, 7)
                if chk and chk.isChecked():
                    sel = table.item(r, 0).text()
                    break
            if not sel:
                return
            
            prog_dlg = ProgressDialog("Обновление", "Подождите, идёт обновление базы данных...", dlg)
            prog_dlg.show()
            QApplication.processEvents()
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT category, property_type, rooms, district, landmark, area, floor, floors_total, price FROM archive_ads WHERE ad_number=%s", (sel,))
                rec = cursor.fetchone()
                if rec:
                    cat, p_type, r_val, dist, land, area_v, floor_v, f_tot, price_v = rec
                    cursor.execute('''
                        INSERT INTO ads (ad_number, category, property_type, rooms, district, landmark, area, floor, floors_total, price, is_active)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
                        ON CONFLICT (ad_number) DO UPDATE SET is_active=1
                    ''', (sel, cat, p_type, r_val, dist, land, area_v, floor_v, f_tot, price_v))
                    cursor.execute("DELETE FROM archive_ads WHERE ad_number=%s", (sel,))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    prog_dlg.close()
                    logging.info(f"Пользователь {self.user_info['username']} восстановил объявление № {sel} (хост: 37.187.139.87).")
                    QMessageBox.information(dlg, "Успех", f"Запись № {sel} восстановлена!")
                    dlg.accept()
                    self.load_table_data()
            except Exception as e:
                prog_dlg.close()
                logging.error(f"Ошибка при восстановлении (хост: 37.187.139.87): {e}")
                QMessageBox.critical(dlg, "Ошибка", f"{e}")

        btn = QPushButton("🔄 Восстановить выбранную запись")
        btn.clicked.connect(restore)
        lay.addWidget(btn)
        dlg.setLayout(lay)
        dlg.exec()

    def setup_category_tabs(self, parent_tab, category_name):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        sub_tabs = QTabWidget()
        sub_tabs.currentChanged.connect(self.clear_all_checkboxes)
        
        ap_w, hs_w = QWidget(), QWidget()
        sub_tabs.addTab(ap_w, "🏢 Квартиры (Apartments)")
        sub_tabs.addTab(hs_w, "🏠 Дома (Houses)")
        
        self.setup_rooms_tabs(ap_w, category_name, "Apartments")
        self.setup_rooms_tabs(hs_w, category_name, "Houses")
        layout.addWidget(sub_tabs)
        parent_tab.setLayout(layout)

    def setup_rooms_tabs(self, parent_widget, category, prop_type):
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        rooms_tabs = QTabWidget()
        rooms_tabs.currentChanged.connect(self.clear_all_checkboxes)
        
        for r in ["1-room", "2-room", "3-room", "4-room", "5-room"]:
            room_tab = QWidget()
            room_layout = QVBoxLayout()
            room_layout.setContentsMargins(0, 0, 0, 0)
            table = QTableWidget()
            table.setColumnCount(9)
            
            headers = ["Объяв-е №", "Район", "Ориентир", "Комн.", "Этаж", "Этажность", "Цена", "Медиа", "Выбор"]
            if prop_type == "Houses":
                headers[4] = "Площадь"
            table.setHorizontalHeaderLabels(headers)
            self.apply_column_widths(table, prop_type)
            table.setIconSize(QSize(50, 50))
            table.cellDoubleClicked.connect(self.on_table_double_click)
            room_layout.addWidget(table)
            room_tab.setLayout(room_layout)
            rooms_tabs.addTab(room_tab, r.replace("-room", "-комн."))
            setattr(self, f"table_{category}_{prop_type}_{r}", table)
        layout.addWidget(rooms_tabs)
        parent_widget.setLayout(layout)

    def on_table_double_click(self, row, col):
        if col == 7:
            tbl = self.sender()
            ad_num_item = tbl.item(row, 0)
            if ad_num_item:
                ad_num = ad_num_item.text()
                self.show_ad_media(ad_num)

    def show_ad_media(self, ad_num):
        ad_cache_dir = os.path.join(self.session_temp_dir, f"ad_{ad_num}")
        media_list = []
        
        if os.path.exists(ad_cache_dir) and os.listdir(ad_cache_dir):
            try:
                for fname in os.listdir(ad_cache_dir):
                    fpath = os.path.join(ad_cache_dir, fname)
                    if os.path.isfile(fpath):
                        media_list.append((fpath, fname))
            except Exception:
                media_list = []

        if not media_list:
            dlg_status = ProgressDialog("Загрузка", "Подождите, идёт загрузка данных в просмотрщик Медиа-файлов...", self)
            dlg_status.show()
            QApplication.processEvents()
            
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT file_name, file_data FROM ad_media WHERE ad_number=%s", (ad_num,))
                rows = cursor.fetchall()
                cursor.close()
                conn.close()
                dlg_status.close()

                if not rows:
                    QMessageBox.information(self, "Медиа", f"У объявления № {ad_num} нет сохраненных файлов.")
                    return

                os.makedirs(ad_cache_dir, exist_ok=True)
                for file_name, binary_data in rows:
                    fpath = os.path.join(ad_cache_dir, file_name)
                    with open(fpath, "wb") as f:
                        f.write(bytes(binary_data))
                    media_list.append((fpath, file_name))
            except Exception as e:
                dlg_status.close()
                QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить медиафайлы: {e}")
                return

        if media_list:
            dlg = ImageViewerDialog(media_list, ad_num, self)
            dlg.exec()

    def enable_creation(self):
        for field in self.inputs.values():
            field.setEnabled(True)
            field.clear()
        QMessageBox.information(self, "Создание", "Панель ввода разблокирована. Заполните данные и нажмите 'Сохранить'.")

    def keyPressEvent(self, event):
        fields_active = list(self.inputs.values())[0].isEnabled()
        if (event.modifiers() & Qt.KeyboardModifier.ControlModifier) and event.key() == Qt.Key.Key_V and fields_active:
            clipboard = QApplication.clipboard()
            text = clipboard.text().strip()
            if text:
                row_data = text.split('\n')[0].split('\t')
                keys = ["ad_number", "district", "landmark", "rooms", "floor_area", "floors_total", "price"]
                for i, key in enumerate(keys):
                    if i < len(row_data) and key in self.inputs:
                        self.inputs[key].setText(row_data[i].strip())
                event.accept()
                return
        super().keyPressEvent(event)

    def enable_editing(self):
        selected_records = []
        rooms_list = ["1-room", "2-room", "3-room", "4-room", "5-room"]
        categories = [("Rent", "Apartments"), ("Rent", "Houses"), ("Sales", "Apartments"), ("Sales", "Houses")]
        
        for cat, pt in categories:
            for r in rooms_list:
                tbl = getattr(self, f"table_{cat}_{pt}_{r}", None)
                if tbl:
                    for row in range(tbl.rowCount()):
                        chk = tbl.cellWidget(row, 8)
                        if chk and chk.isChecked():
                            selected_records.append((tbl, row))
        
        if len(selected_records) > 1:
            QMessageBox.warning(self, "Внимание", "Можно одновременно изменить только одно объявление!")
            return
        if not selected_records:
            QMessageBox.warning(self, "Внимание", "Отметьте запись галочкой!")
            return

        tbl, row = selected_records[0]
        selected_record = {
            "ad_number": tbl.item(row, 0).text(),
            "district": tbl.item(row, 1).text(),
            "landmark": tbl.item(row, 2).text(),
            "rooms": tbl.item(row, 3).text(),
            "floor_area": tbl.item(row, 4).text(),
            "floors_total": tbl.item(row, 5).text(),
            "price": tbl.item(row, 6).text()
        }

        for key, field in self.inputs.items():
            field.setEnabled(True)
            if key in selected_record:
                field.setText(selected_record[key])

        QMessageBox.information(self, "Изменение", f"Объявление № {selected_record['ad_number']} загружено в панель ввода.")

    def save_data(self):
        ad_num = self.inputs["ad_number"].text().strip()
        rooms = self.inputs["rooms"].text().strip().replace("-room", "").replace("-комн.", "").strip()
        district = self.inputs["district"].text().strip()
        landmark = self.inputs["landmark"].text().strip()
        
        try:
            fa_text = self.inputs["floor_area"].text().strip().replace(" ", "")
            fa = int(fa_text) if fa_text else 0
            ft = int(self.inputs["floors_total"].text().strip().replace(" ", "")) if self.inputs["floors_total"].text().strip() else 1
            pr = float(self.inputs["price"].text().strip().replace(" ", "").replace(",", ".")) if self.inputs["price"].text().strip() else 0.0
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Проверьте числовые поля!")
            return

        if not ad_num:
            QMessageBox.warning(self, "Ошибка", "Введите номер объявления!")
            return

        dlg_status = ProgressDialog("Обновление", "Подождите, идёт обновление базы данных...", self)
        dlg_status.show()
        QApplication.processEvents()

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ads (ad_number, category, property_type, rooms, district, landmark, floor, floors_total, price, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
                ON CONFLICT (ad_number) DO UPDATE SET district=%s, landmark=%s, floor=%s, floors_total=%s, price=%s, is_active=1
            ''', (ad_num, "Rent", "Apartments", rooms, district, landmark, fa, ft, pr, district, landmark, fa, ft, pr))
            conn.commit()
            cursor.close()
            conn.close()
            dlg_status.close()
            QMessageBox.information(self, "Успех", "Данные успешно сохранены!")
            self.load_table_data()
        except Exception as e:
            dlg_status.close()
            QMessageBox.critical(self, "Ошибка БД", f"{e}")

        for field in self.inputs.values():
            field.clear()
            field.setEnabled(False)

    def upload_media(self):
        selected_ad_num = None
        rooms_list = ["1-room", "2-room", "3-room", "4-room", "5-room"]
        categories = [("Rent", "Apartments"), ("Rent", "Houses"), ("Sales", "Apartments"), ("Sales", "Houses")]
        
        checked_count = 0
        for cat, pt in categories:
            for r in rooms_list:
                tbl = getattr(self, f"table_{cat}_{pt}_{r}", None)
                if tbl:
                    for row in range(tbl.rowCount()):
                        chk = tbl.cellWidget(row, 8)
                        if chk and chk.isChecked():
                            checked_count += 1
                            item = tbl.item(row, 0)
                            if item:
                                selected_ad_num = item.text().strip()

        if checked_count > 1 or not selected_ad_num:
            QMessageBox.warning(self, "Внимание", "Выберите ровно один объект для прикрепления файлов!")
            return

        file_paths, _ = QFileDialog.getOpenFileNames(self, f"Файлы для № {selected_ad_num}", "", "Медиа (*.png *.jpg *.jpeg *.mp4 *.avi *.mov);;Все (*.*)")
        if not file_paths:
            return

        total_size_mb = sum(os.path.getsize(f) for f in file_paths if os.path.exists(f)) / (1024 * 1024)
        if total_size_mb > 50.0:
            QMessageBox.critical(self, "Ошибка", f"Объем файлов ({total_size_mb:.1f} МБ) превышает лимит в 50 МБ!")
            return

        dlg_status = ProgressDialog("Загрузка", "Отправка файлов на сервер...", self)
        dlg_status.show()
        QApplication.processEvents()

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            ad_cache_dir = os.path.join(self.session_temp_dir, f"ad_{selected_ad_num}")
            os.makedirs(ad_cache_dir, exist_ok=True)

            for file_path in file_paths:
                file_name = os.path.basename(file_path)
                with open(file_path, "rb") as f:
                    binary_data = f.read()
                cursor.execute("INSERT INTO ad_media (ad_number, file_name, file_data) VALUES (%s, %s, %s)", (selected_ad_num, file_name, psycopg2.Binary(binary_data)))
                shutil.copy2(file_path, os.path.join(ad_cache_dir, file_name))
                QApplication.processEvents()
                
            conn.commit()
            cursor.close()
            conn.close()
            dlg_status.close()
            QMessageBox.information(self, "Успех", "Файлы успешно загружены!")
            self.load_table_data()
        except Exception as e:
            dlg_status.close()
            QMessageBox.critical(self, "Ошибка", f"{e}")

    def delete_records(self):
        rooms_list = ["1-room", "2-room", "3-room", "4-room", "5-room"]
        categories = [("Rent", "Apartments"), ("Rent", "Houses"), ("Sales", "Apartments"), ("Sales", "Houses")]
        checked = []
        for cat, pt in categories:
            for r in rooms_list:
                tbl = getattr(self, f"table_{cat}_{pt}_{r}", None)
                if tbl:
                    for row in range(tbl.rowCount()):
                        chk = tbl.cellWidget(row, 8)
                        if chk and chk.isChecked():
                            checked.append(tbl.item(row, 0).text())
        if not checked or len(checked) > 1:
            QMessageBox.warning(self, "Ошибка", "Отметьте ровно одну запись!")
            return
            
        if QMessageBox.question(self, "Удаление", f"Удалить объявление № {checked[0]}?") == QMessageBox.StandardButton.Yes:
            dlg_status = ProgressDialog("Обновление", "Обновление базы данных...", self)
            dlg_status.show()
            QApplication.processEvents()
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("SELECT category, property_type, rooms, district, landmark, area, floor, floors_total, price FROM ads WHERE ad_number=%s", (checked[0],))
                rec = cursor.fetchone()
                if rec:
                    c, pt, r_v, d, l, a, fl, ft, pr = rec
                    cursor.execute('''
                        INSERT INTO archive_ads (ad_number, category, property_type, rooms, district, landmark, area, floor, floors_total, price, deleted_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (ad_number) DO NOTHING
                    ''', (checked[0], c, pt, r_v, d, l, a, fl, ft, pr, now_str))
                cursor.execute("UPDATE ads SET is_active=0 WHERE ad_number=%s", (checked[0],))
                conn.commit()
                cursor.close()
                conn.close()
                dlg_status.close()
                QMessageBox.information(self, "Успех", "Объявление удалено в архив!")
                self.load_table_data()
            except Exception as e:
                dlg_status.close()
                QMessageBox.critical(self, "Ошибка", f"{e}")

    def delete_multiple_records(self):
        rooms_list = ["1-room", "2-room", "3-room", "4-room", "5-room"]
        categories = [("Rent", "Apartments"), ("Rent", "Houses"), ("Sales", "Apartments"), ("Sales", "Houses")]
        checked = []
        for cat, pt in categories:
            for r in rooms_list:
                tbl = getattr(self, f"table_{cat}_{pt}_{r}", None)
                if tbl:
                    for row in range(tbl.rowCount()):
                        chk = tbl.cellWidget(row, 8)
                        if chk and chk.isChecked():
                            checked.append(tbl.item(row, 0).text())
                            
        if not checked:
            QMessageBox.warning(self, "Внимание", "Отметьте записи для удаления!")
            return
            
        if QMessageBox.question(self, "Удаление", f"Удалить выбранные записи ({len(checked)} шт.)?") == QMessageBox.StandardButton.Yes:
            dlg_status = ProgressDialog("Обновление", "Обновление базы данных...", self)
            dlg_status.show()
            QApplication.processEvents()
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                for ad in checked:
                    cursor.execute("SELECT category, property_type, rooms, district, landmark, area, floor, floors_total, price FROM ads WHERE ad_number=%s", (ad,))
                    rec = cursor.fetchone()
                    if rec:
                        c, pt, r_v, d, l, a, fl, ft, pr = rec
                        cursor.execute('''
                            INSERT INTO archive_ads (ad_number, category, property_type, rooms, district, landmark, area, floor, floors_total, price, deleted_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (ad_number) DO NOTHING
                        ''', (ad, c, pt, r_v, d, l, a, fl, ft, pr, now_str))
                    cursor.execute("UPDATE ads SET is_active=0 WHERE ad_number=%s", (ad,))
                conn.commit()
                cursor.close()
                conn.close()
                dlg_status.close()
                QMessageBox.information(self, "Успех", f"Удалено записей: {len(checked)}")
                self.load_table_data()
            except Exception as e:
                dlg_status.close()
                QMessageBox.critical(self, "Ошибка", f"{e}")

    def load_table_data(self):
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            rooms_list = ["1-room", "2-room", "3-room", "4-room", "5-room"]
            categories = [("Rent", "Apartments"), ("Rent", "Houses"), ("Sales", "Apartments"), ("Sales", "Houses")]
            
            for cat, pt in categories:
                for r in rooms_list:
                    tbl = getattr(self, f"table_{cat}_{pt}_{r}", None)
                    if tbl:
                        r_val = r.replace("-room", "").strip()
                        cursor.execute(
                            "SELECT ad_number, district, landmark, rooms, floor, floors_total, price FROM ads WHERE category=%s AND property_type=%s AND rooms=%s AND is_active=1 ORDER BY ad_number::integer ASC, ad_number ASC",
                            (cat, pt, r_val)
                        )
                        rows = cursor.fetchall()
                        tbl.setRowCount(len(rows))
                        for r_idx, r_data in enumerate(rows):
                            row_list = list(r_data)
                            for c_idx, val in enumerate(row_list):
                                tbl.setItem(r_idx, c_idx, QTableWidgetItem(str(val)))
                            
                            ad_num = r_data[0]
                            cursor.execute("SELECT file_name FROM ad_media WHERE ad_number=%s", (ad_num,))
                            media_files = cursor.fetchall()
                            img_count = sum(1 for (f,) in media_files if f.lower().split('.')[-1] in ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif'])
                            video_count = sum(1 for (f,) in media_files if f.lower().split('.')[-1] in ['mp4', 'avi', 'mov', 'mkv', 'flv', 'wmv'])
                            
                            parts = []
                            if img_count > 0:
                                parts.append(f"🖼️ Фото: {img_count}")
                            if video_count > 0:
                                parts.append(f"📹 Видео: {video_count}")
                            
                            media_label = QLabel("Нет медиа" if not parts else " | ".join(parts))
                            media_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                            tbl.setCellWidget(r_idx, 7, media_label)
                            tbl.setCellWidget(r_idx, 8, QCheckBox())
            cursor.close()
            conn.close()
        except Exception as e:
            logging.error(f"Ошибка загрузки данных таблиц: {e}")

# Глобальные ссылки для организации бесконечного цикла авторизации/смены пользователя
auth_global = None
window_global = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    if os.name == 'win32':
        try:
            ctypes.windll.user32.ShowWindow(ctypes.windll.kernel32.GetConsoleWindow(), 0)
        except:
            pass

    try:
        init_db()
    except Exception as e:
        print(f"Ошибка инициализации БД: {e}")

    # Запускаем цикл входа/смены пользователя
    while True:
        auth_global = AuthWindow()
        if auth_global.exec() == QDialog.DialogCode.Accepted and auth_global.user_data:
            window_global = MainWindow(auth_global.user_data)
            window_global.show()
            app.exec()
            
            if not getattr(window_global, "switch_user_requested", False):
                break
        else:
            break

    sys.exit(0)