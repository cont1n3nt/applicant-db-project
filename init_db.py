#!/usr/bin/env python
"""
Скрипт для инициализации базы данных
"""

from app import app
from models import db

def init_database():
    """
    Создает таблицы в базе данных
    """
    with app.app_context():
        print("Создание таблиц базы данных...")
        db.create_all()
        print("✅ Таблицы успешно созданы!")
        
        # Проверка
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        print(f"\nСозданные таблицы: {', '.join(tables)}")

if __name__ == "__main__":
    init_database()
