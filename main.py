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

# ==================== НАСТРОЙКИ ====================
app = FastAPI(title="Game School MVP")

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

@app.post("/api/bookings")
async def create_booking(booking: BookingCreate, request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ? AND status = 'available'", (booking.session_id,))
        session = cursor.fetchone()
        if not session:
            raise HTTPException(status_code=404, detail="Session not available")
        
        cursor.execute("""
            INSERT INTO bookings (user_id, session_id, status)
            VALUES (?, ?, ?)
        """, (user["id"], booking.session_id, "confirmed"))
        booking_id = cursor.lastrowid
        
        conn.commit()
        return {"id": booking_id, "status": "confirmed", "message": "Booking confirmed!"}

@app.get("/api/bookings")
async def get_my_bookings(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT b.id, b.status, b.created_at, s.title, s.price, s.start_time, u.name as coach_name
            FROM bookings b
            JOIN sessions s ON b.session_id = s.id
            JOIN users u ON s.coach_id = u.id
            WHERE b.user_id = ?
            ORDER BY b.created_at DESC
        """, (user["id"],))
        bookings = [dict(row) for row in cursor.fetchall()]
        return bookings

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