import csv
import random
from pathlib import Path

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

programs = ["PM", "IVT", "ITSS", "IB"]

# Количество абитуриентов по дням (по ТЗ минимально, можно увеличить)
counts = {
    "01_08": [60, 100, 50, 70],
    "02_08": [380, 370, 350, 260],
    "03_08": [1000, 1150, 1050, 800],
    "04_08": [1240, 1390, 1240, 1190],
}

for date, day_counts in counts.items():
    rows = []
    global_id = 1000  # начальный id, можно любой
    for program, count in zip(programs, day_counts):
        for _ in range(count):
            physics = random.randint(50, 100)
            rus = random.randint(50, 100)
            math = random.randint(50, 100)
            extra = random.randint(0, 10)
            total = physics + rus + math + extra
            priority = random.randint(1, 4)
            consent = random.randint(0, 1)
            rows.append({
                "id": global_id,
                "program": program,
                "priority": priority,
                "physics": physics,
                "rus": rus,
                "math": math,
                "extra": extra,
                "total": total,
                "consent": consent
            })
            global_id += 1
    
    filepath = DATA_DIR / f"{date}.csv"
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id","program","priority","physics","rus","math","extra","total","consent"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV {filepath} создано, записано {len(rows)} абитуриентов")
