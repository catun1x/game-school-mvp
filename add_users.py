import sqlite3
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Подключение к БД
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# Список пользователей для добавления
users = [
    ("Дмитрий Кузнецов", "dmitry@example.com", "coach", "CS2", 4.9, 1500, 4, "Профессиональный тренер по CS2"),
    ("Анна Соколова", "anna@example.com", "coach", "Valorant", 4.8, 1300, 3, "Тренер по Valorant, помогаю поднять ранг"),
    ("Сергей Морозов", "sergey@example.com", "player", None, None, None, None, None),
    ("Елена Новикова", "elena@example.com", "player", None, None, None, None, None),
    ("Максим Волков", "maxim@example.com", "coach", "Dota 2", 4.7, 1400, 5, "Тренер по Dota 2, MMR 6000+"),
    ("Ольга Зайцева", "olga@example.com", "player", None, None, None, None, None),
    ("Артём Павлов", "artem@example.com", "coach", "League of Legends", 4.9, 1600, 4, "Тренер по LoL, Diamond+"),
    ("Наталья Егорова", "natalia@example.com", "player", None, None, None, None, None),
    ("Игорь Тимофеев", "igor@example.com", "coach", "CS2", 4.6, 1200, 3, "Тренер по CS2, акцент на aim и тактику"),
    ("Мария Фёдорова", "maria@example.com", "player", None, None, None, None, None),
    ("Павел Никитин", "pavel@example.com", "coach", "Valorant", 4.8, 1350, 3, "Тренер по Valorant, бывший Immortal"),
    ("Татьяна Григорьева", "tatyana@example.com", "player", None, None, None, None, None),
    ("Андрей Соловьёв", "andrey@example.com", "coach", "Dota 2", 4.7, 1250, 4, "Тренер по Dota 2, позиция керри"),
    ("Юлия Васильева", "yulia@example.com", "player", None, None, None, None, None),
]

password_hash = pwd_context.hash("test123")

for user in users:
    name, email, role, game, rating, price, exp, desc = user
    
    # Добавляем пользователя
    cursor.execute("""
        INSERT INTO users (name, email, password_hash, role, status)
        VALUES (?, ?, ?, ?, ?)
    """, (name, email, password_hash, role, "active"))
    user_id = cursor.lastrowid
    
    # Если тренер — добавляем профиль
    if role == "coach":
        cursor.execute("""
            INSERT INTO coach_profiles (user_id, game, rating, price_per_hour, experience_years, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, game, rating, price, exp, desc))
    
    # Если игрок — добавляем профиль
    else:
        cursor.execute("""
            INSERT INTO player_profiles (user_id, nickname, level, preferred_game)
            VALUES (?, ?, ?, ?)
        """, (user_id, name, "Средний", "Не указана"))

conn.commit()
conn.close()

print("✅ Добавлено 14 пользователей!")