import os

class Config:
    """
    Конфигурация приложения
    """
    # Секретный ключ для Flask сессий
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Конфигурация базы данных SQLite
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///applicants.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Папки для данных
    DATA_DIR = 'data'
    REPORTS_DIR = 'reports'
    
    # Максимальный размер файла (5MB)
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    
    # Образовательные программы согласно п.6 технических требований
    PROGRAMS = {
        "pm": {
            "name": "Прикладная математика",
            "seats": 40,
            "full_name": "ПМ"
        },
        "ivt": {
            "name": "Информатика и вычислительная техника",
            "seats": 50,
            "full_name": "ИВТ"
        },
        "itss": {
            "name": "Инфокоммуникационные технологии и системы связи",
            "seats": 30,
            "full_name": "ИТСС"
        },
        "ib": {
            "name": "Информационная безопасность",
            "seats": 20,
            "full_name": "ИБ"
        }
    }
