from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Optional
import sqlite3
from datetime import datetime, timedelta
from contextlib import contextmanager
from passlib.context import CryptContext
from jose import JWTError, jwt
import requests

# ==================== НАСТРОЙКИ ====================
app = FastAPI(title="Game School MVP")

# ВЕБХУК BITRIX24 (правильный URL для API)
BITRIX24_WEBHOOK = "https://b24-38mywy.bitrix24.ru/rest/1/373163c75fajqjgk/"

# Коды кастомных полей (из JSON)
UF_PLAYER = "UF_CRM_1777380108"        # Игрок
UF_EMAIL = "UF_CRM_1777380170"         # Email игрока
UF_COACH = "UF_CRM_1777380197"         # Тренер
UF_SESSION_TITLE = "UF_CRM_1777380219" # Название занятия
UF_SESSION_TIME = "UF_CRM_1777380430"  # Дата и время
UF_PRICE = "UF_CRM_1777380577"         # Цена
UF_STATUS = "UF_CRM_1777381454"        # Статус сделки

# ID статусов
STATUS_CONFIRMED = 64

# Подключаем статику (CSS) и шаблоны (HTML)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Настройка паролей и JWT
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = "your-secret-key-change-in-production"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 дней

# ==================== БАЗА ДАННЫХ ====================
DATABASE_PATH = "database.db"

@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'player',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'active'
            )
        """)
        
        # Таблица профилей тренеров
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS coach_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                description TEXT,
                experience_years INTEGER DEFAULT 0,
                game TEXT,
                rating REAL DEFAULT 0,
                price_per_hour INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # Таблица профилей игроков
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE NOT NULL,
                nickname TEXT,
                level TEXT,
                preferred_game TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # Таблица занятий
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                coach_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                game TEXT,
                duration INTEGER DEFAULT 60,
                price INTEGER DEFAULT 0,
                start_time TIMESTAMP,
                max_participants INTEGER DEFAULT 1,
                status TEXT DEFAULT 'available',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (coach_id) REFERENCES users (id)
            )
        """)
        
        # Таблица бронирований
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bookings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                session_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (session_id) REFERENCES sessions (id)
            )
        """)
        
        conn.commit()
    
    # Добавляем тестовые данные
    create_test_data()

def create_test_data():
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Проверяем, есть ли уже данные
        cursor.execute("SELECT COUNT(*) FROM users")
        if cursor.fetchone()[0] > 0:
            return
        
        password_hash = pwd_context.hash("test123")
        
        # Тренер 1 (CS2)
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        """, ("Алексей Смирнов", "alexey@example.com", password_hash, "coach"))
        coach1_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO coach_profiles (user_id, description, experience_years, game, rating, price_per_hour)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (coach1_id, "Профессиональный тренер по CS2, опыт на профессиональной сцене", 5, "CS2", 4.9, 1500))
        
        # Тренер 2 (Dota 2)
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        """, ("Екатерина Волкова", "ekaterina@example.com", password_hash, "coach"))
        coach2_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO coach_profiles (user_id, description, experience_years, game, rating, price_per_hour)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (coach2_id, "Тренер по Dota 2, помогаю поднять MMR", 3, "Dota 2", 4.8, 1200))
        
        # Игрок
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        """, ("Иван Петров", "ivan@example.com", password_hash, "player"))
        player_id = cursor.lastrowid
        
        cursor.execute("""
            INSERT INTO player_profiles (user_id, nickname, level, preferred_game)
            VALUES (?, ?, ?, ?)
        """, (player_id, "IvanPro", "Средний", "CS2"))
        
        # Занятия
        cursor.execute("""
            INSERT INTO sessions (coach_id, title, description, game, duration, price, start_time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (coach1_id, "Индивидуальная тренировка CS2", "Разбор демок, отработка aim", "CS2", 60, 1500, datetime.now() + timedelta(days=1), "available"))
        
        cursor.execute("""
            INSERT INTO sessions (coach_id, title, description, game, duration, price, start_time, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (coach2_id, "Dota 2: повышение MMR", "Анализ пиков, позиционирование", "Dota 2", 90, 1200, datetime.now() + timedelta(days=2), "available"))
        
        conn.commit()

# ==================== ФУНКЦИИ АВТОРИЗАЦИИ ====================
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, role FROM users WHERE id = ?", (payload.get("user_id"),))
        user = cursor.fetchone()
        return dict(user) if user else None
    
# ==================== ФУНКЦИЯ СОЗДАНИЯ КОНТАКТА В BITRIX24 ====================

def create_contact_in_bitrix24(contact_data: dict):
    """Создаёт контакт в Bitrix24 (игрока)"""
    
    contact_fields = {
        "fields": {
            "NAME": contact_data['player_name'],
            "EMAIL": [{"VALUE": contact_data['player_email'], "VALUE_TYPE": "WORK"}],
        }
    }
    
    try:
        response = requests.post(
            f"{BITRIX24_WEBHOOK}crm.contact.add",
            json=contact_fields,
            timeout=10
        )
        result = response.json()
        
        if "error" in result:
            print(f"Ошибка создания контакта: {result}")
            return None
        else:
            contact_id = result['result']
            print(f"✅ Контакт создан! ID: {contact_id}")
            return contact_id
            
    except Exception as e:
        print(f"❌ Ошибка создания контакта: {e}")
        return None

# ==================== ФУНКЦИЯ ОТПРАВКИ СДЕЛКИ В BITRIX24 ====================

def send_deal_to_bitrix24(booking_data: dict):
    """Отправляет данные о бронировании в Bitrix24 с привязкой к контакту"""
    
    # 1. Сначала создаём контакт (игрока)
    contact_id = create_contact_in_bitrix24({
        "player_name": booking_data['player_name'],
        "player_email": booking_data['player_email']
    })
    
    # 2. Создаём сделку и привязываем к контакту
    deal_fields = {
        "fields": {
            "TITLE": f"{booking_data['player_name']} - {booking_data['session_title']}",
            "CONTACT_ID": contact_id,  # ПРИВЯЗКА К КОНТАКТУ (для email робота)
            UF_PLAYER: booking_data['player_name'],
            UF_EMAIL: booking_data['player_email'],
            UF_COACH: booking_data['coach_name'],
            UF_SESSION_TITLE: booking_data['session_title'],
            UF_SESSION_TIME: booking_data['session_time'],
            UF_PRICE: f"{booking_data['price']}|RUB",  # money формат
            UF_STATUS: STATUS_CONFIRMED,
        }
    }
    
    try:
        response = requests.post(
            f"{BITRIX24_WEBHOOK}crm.deal.add",
            json=deal_fields,
            timeout=10
        )
        result = response.json()
        
        if "error" in result:
            print(f"Ошибка Bitrix24: {result}")
        else:
            print(f"✅ Сделка создана! ID: {result['result']} для контакта {contact_id}")
            
    except Exception as e:
        print(f"❌ Ошибка отправки в CRM: {e}")

# ==================== PYDANTIC МОДЕЛИ ====================
class UserRegister(BaseModel):
    name: str
    email: str
    password: str
    role: str = "player"

class UserLogin(BaseModel):
    email: str
    password: str

class BookingCreate(BaseModel):
    session_id: int

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    game: Optional[str] = None
    description: Optional[str] = None
    experience_years: Optional[int] = None
    price_per_hour: Optional[int] = None
    nickname: Optional[str] = None
    level: Optional[str] = None
    preferred_game: Optional[str] = None

# ==================== API ЭНДПОИНТЫ ====================
@app.post("/api/register")
async def register(user: UserRegister):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email = ?", (user.email,))
        if cursor.fetchone():
            raise HTTPException(status_code=400, detail="Email already registered")
        
        password_hash = get_password_hash(user.password)
        cursor.execute("""
            INSERT INTO users (name, email, password_hash, role)
            VALUES (?, ?, ?, ?)
        """, (user.name, user.email, password_hash, user.role))
        user_id = cursor.lastrowid
        
        if user.role == "coach":
            cursor.execute("""
                INSERT INTO coach_profiles (user_id, description, experience_years, game)
                VALUES (?, ?, ?, ?)
            """, (user_id, "", 0, ""))
        else:
            cursor.execute("""
                INSERT INTO player_profiles (user_id, nickname, level, preferred_game)
                VALUES (?, ?, ?, ?)
            """, (user_id, user.name, "Начинающий", ""))
        
        conn.commit()
        
        token = create_access_token({"user_id": user_id, "role": user.role})
        return {"access_token": token, "user_id": user_id, "role": user.role}

@app.post("/api/login")
async def login(user: UserLogin):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, password_hash, role FROM users WHERE email = ?", (user.email,))
        db_user = cursor.fetchone()
        if not db_user or not verify_password(user.password, db_user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        token = create_access_token({"user_id": db_user["id"], "role": db_user["role"]})
        return {"access_token": token, "user_id": db_user["id"], "role": db_user["role"]}

@app.get("/api/coaches")
async def get_coaches(game: Optional[str] = None):
    with get_db() as conn:
        cursor = conn.cursor()
        query = """
            SELECT u.id, u.name, cp.description, cp.experience_years, cp.game, cp.rating, cp.price_per_hour
            FROM users u
            JOIN coach_profiles cp ON u.id = cp.user_id
            WHERE u.role = 'coach' AND u.status = 'active'
        """
        params = []
        if game:
            query += " AND cp.game LIKE ?"
            params.append(f"%{game}%")
        cursor.execute(query, params)
        coaches = [dict(row) for row in cursor.fetchall()]
        return coaches

@app.get("/api/coaches/{coach_id}")
async def get_coach(coach_id: int):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.name, cp.description, cp.experience_years, cp.game, cp.rating, cp.price_per_hour
            FROM users u
            JOIN coach_profiles cp ON u.id = cp.user_id
            WHERE u.id = ? AND u.role = 'coach'
        """, (coach_id,))
        coach = cursor.fetchone()
        if not coach:
            raise HTTPException(status_code=404, detail="Coach not found")
        
        cursor.execute("""
            SELECT id, title, description, duration, price, start_time, status
            FROM sessions
            WHERE coach_id = ? AND status = 'available'
        """, (coach_id,))
        sessions = [dict(row) for row in cursor.fetchall()]
        
        return {"coach": dict(coach), "sessions": sessions}

# ==================== ГЛАВНЫЙ ЭНДПОИНТ БРОНИРОВАНИЯ С CRM ====================
@app.post("/api/bookings")
async def create_booking(booking: BookingCreate, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Получаем занятие и имя тренера
        cursor.execute("""
            SELECT s.*, u.name as coach_name
            FROM sessions s
            JOIN users u ON s.coach_id = u.id
            WHERE s.id = ? AND s.status = 'available'
        """, (booking.session_id,))
        
        session = cursor.fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="Session not available")
        
        # Создаем бронирование
        cursor.execute("""
            INSERT INTO bookings (user_id, session_id, status)
            VALUES (?, ?, ?)
        """, (user["id"], booking.session_id, "confirmed"))
        booking_id = cursor.lastrowid
        
        conn.commit()
        
        # Отправляем данные в Bitrix24 CRM
        send_deal_to_bitrix24({
            "player_name": user["name"],
            "player_email": user["email"],
            "coach_name": session["coach_name"],
            "session_title": session["title"],
            "session_time": str(session["start_time"]),
            "price": session["price"]
        })
        
        return {
            "id": booking_id, 
            "status": "confirmed", 
            "message": "Booking confirmed and sent to CRM!"
        }

# НОВЫЙ ЭНДПОИНТ: тренер видит записи к себе
@app.get("/api/coaches/bookings")
async def get_coach_bookings(request: Request):
    user = get_current_user(request)
    if not user or user["role"] != "coach":
        raise HTTPException(status_code=403, detail="Access denied. Only for coaches")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id, b.status, b.created_at, s.title, s.price, s.start_time, 
                   u.name as student_name, u.email as student_email
            FROM bookings b
            JOIN sessions s ON b.session_id = s.id
            JOIN users u ON b.user_id = u.id
            WHERE s.coach_id = ?
            ORDER BY b.created_at DESC
        """, (user["id"],))
        bookings = [dict(row) for row in cursor.fetchall()]
        return {"bookings": bookings}

@app.get("/api/profile")
async def get_profile(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    with get_db() as conn:
        cursor = conn.cursor()
        if user["role"] == "coach":
            cursor.execute("SELECT * FROM coach_profiles WHERE user_id = ?", (user["id"],))
            profile = cursor.fetchone()
        else:
            cursor.execute("SELECT * FROM player_profiles WHERE user_id = ?", (user["id"],))
            profile = cursor.fetchone()
        
        return {"user": user, "profile": dict(profile) if profile else None}

@app.put("/api/profile")
async def update_profile(profile_data: ProfileUpdate, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    with get_db() as conn:
        cursor = conn.cursor()
        
        # Обновляем основную информацию пользователя
        if profile_data.name:
            cursor.execute("UPDATE users SET name = ? WHERE id = ?", (profile_data.name, user["id"]))
        
        # Обновляем профиль в зависимости от роли
        if user["role"] == "coach":
            updates = []
            params = []
            if profile_data.game is not None:
                updates.append("game = ?")
                params.append(profile_data.game)
            if profile_data.description is not None:
                updates.append("description = ?")
                params.append(profile_data.description)
            if profile_data.experience_years is not None:
                updates.append("experience_years = ?")
                params.append(profile_data.experience_years)
            if profile_data.price_per_hour is not None:
                updates.append("price_per_hour = ?")
                params.append(profile_data.price_per_hour)
            
            if updates:
                params.append(user["id"])
                cursor.execute(f"UPDATE coach_profiles SET {', '.join(updates)} WHERE user_id = ?", params)
        else:
            updates = []
            params = []
            if profile_data.nickname is not None:
                updates.append("nickname = ?")
                params.append(profile_data.nickname)
            if profile_data.level is not None:
                updates.append("level = ?")
                params.append(profile_data.level)
            if profile_data.preferred_game is not None:
                updates.append("preferred_game = ?")
                params.append(profile_data.preferred_game)
            
            if updates:
                params.append(user["id"])
                cursor.execute(f"UPDATE player_profiles SET {', '.join(updates)} WHERE user_id = ?", params)
        
        conn.commit()
        
        # Возвращаем обновлённый профиль
        if user["role"] == "coach":
            cursor.execute("SELECT * FROM coach_profiles WHERE user_id = ?", (user["id"],))
            profile = cursor.fetchone()
        else:
            cursor.execute("SELECT * FROM player_profiles WHERE user_id = ?", (user["id"],))
            profile = cursor.fetchone()
        
        cursor.execute("SELECT id, name, email, role FROM users WHERE id = ?", (user["id"],))
        updated_user = cursor.fetchone()
        
        return {"user": dict(updated_user), "profile": dict(profile) if profile else None}

# ==================== HTML СТРАНИЦЫ ====================
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    user = get_current_user(request)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("register.html", {"request": request})

@app.get("/coaches", response_class=HTMLResponse)
async def coaches_page(request: Request, game: str = ""):
    user = get_current_user(request)
    return templates.TemplateResponse("coaches.html", {"request": request, "user": user, "game_filter": game})

@app.get("/coaches/{coach_id}", response_class=HTMLResponse)
async def coach_detail_page(request: Request, coach_id: int):
    user = get_current_user(request)
    return templates.TemplateResponse("coach_detail.html", {"request": request, "user": user, "coach_id": coach_id})

@app.get("/booking/{session_id}", response_class=HTMLResponse)
async def booking_page(request: Request, session_id: int):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("booking.html", {"request": request, "user": user, "session_id": session_id})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})

@app.post("/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("access_token")
    return response

@app.get("/api/users")
async def get_all_users():
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, role, created_at FROM users")
        users = cursor.fetchall()
        return {"users": [dict(user) for user in users]}

# ==================== ЗАПУСК ====================
if __name__ == "__main__":
    import uvicorn
    import os
    init_db()
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)