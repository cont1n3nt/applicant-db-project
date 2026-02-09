import csv
import os
import io
from datetime import datetime
from flask import flash
from models import db, Applicant, PassingScore
from config import Config
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO


PROGRAMS = Config.PROGRAMS
DATA_DIR = Config.DATA_DIR


def get_csv_files():
    """
    Возвращает список CSV файлов в папке data
    """
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
    return sorted(files)


def get_latest_csv():
    """
    Возвращает последний загруженный CSV файл
    """
    files = get_csv_files()
    return files[-1] if files else None


def upload_competition_list(file, date):
    """
    П.2-4: Загрузка и обновление конкурсных списков в БД
    
    Процесс обновления:
    - Если БД пуста - полностью загружаем данные
    - Если БД содержит данные:
      a) Удаляем записи, отсутствующие в новом списке
      b) Добавляем новые записи
      c) Обновляем существующие записи
    
    П.3: Время загрузки не должно превышать 5 секунд
    """
    start_time = datetime.now()
    
    if not file.filename.lower().endswith('.csv'):
        raise ValueError("Можно загружать только CSV файлы")
    
    # Сохраняем файл
    safe_date = date.replace('.', '_').strip()
    filename = f"{safe_date}.csv"
    filepath = os.path.join(DATA_DIR, filename)
    file.save(filepath)
    
    # Читаем CSV
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        new_data = list(reader)
    
    # Получаем существующие записи для этой даты
    existing_applicants = Applicant.query.filter_by(upload_date=safe_date).all()
    existing_ids = {(app.id, app.program_code) for app in existing_applicants}
    
    # Новые ID из CSV
    new_ids = {(int(row['id']), row['program']) for row in new_data}
    
    # П.4.a: Удаление записей, отсутствующих в новом списке
    ids_to_delete = existing_ids - new_ids
    if ids_to_delete:
        for app_id, prog_code in ids_to_delete:
            Applicant.query.filter_by(
                id=app_id, 
                program_code=prog_code, 
                upload_date=safe_date
            ).delete()
    
    # П.4.b и 4.c: Добавление и обновление
    for row in new_data:
        applicant_id = int(row['id'])
        program_code = row['program']
        
        existing = Applicant.query.filter_by(id=applicant_id, upload_date=safe_date).first()
        
        applicant_data = {
            'id': applicant_id,
            'program_code': program_code,
            'priority': int(row['priority']),
            'physics_ict_score': int(row['physics']),
            'russian_score': int(row['rus']),
            'math_score': int(row['math']),
            'extra_score': int(row['extra']),
            'total_score': int(row['total']),
            'has_consent': row['consent'] == '1',
            'upload_date': safe_date
        }
        
        if existing:
            for key, value in applicant_data.items():
                if key != 'id':
                    setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
        else:
            new_applicant = Applicant(**applicant_data)
            db.session.add(new_applicant)

    db.session.commit()
        
    # Проверяем время выполнения
    elapsed_time = (datetime.now() - start_time).total_seconds()
    
    flash(f"Файл {filename} успешно загружен за {elapsed_time:.2f} секунд", "success")
    
    if elapsed_time > 5:
        flash(f"ВНИМАНИЕ: Время загрузки ({elapsed_time:.2f}с) превысило требуемые 5 секунд", "warning")
    
    return True


def get_all_applicants(date=None, sort_by='total_score', order='desc'):
    """
    П.12: Визуализация конкурсных списков
    
    Возвращает список всех абитуриентов с возможностью сортировки и фильтрации
    Время перестроения визуализаций не должно превышать 3 секунды
    """
    start_time = datetime.now()
    
    if not date:
        latest = get_latest_csv()
        date = latest.replace('.csv', '') if latest else None
    
    if not date:
        return []
    
    query = Applicant.query.filter_by(upload_date=date)
    
    # Сортировка
    if sort_by == 'total_score':
        query = query.order_by(Applicant.total_score.desc() if order == 'desc' else Applicant.total_score.asc())
    elif sort_by == 'id':
        query = query.order_by(Applicant.id.asc() if order == 'asc' else Applicant.id.desc())
    elif sort_by == 'priority':
        query = query.order_by(Applicant.priority.asc() if order == 'asc' else Applicant.priority.desc())
    
    applicants = query.all()
    
    result = []
    for app in applicants:
        result.append({
            'id': app.id,
            'program_code': app.program_code,
            'program_name': PROGRAMS[app.program_code]['name'],
            'priority': app.priority,
            'physics_ict': app.physics_ict_score,
            'russian': app.russian_score,
            'math': app.math_score,
            'extra': app.extra_score,
            'total_score': app.total_score,
            'has_consent': app.has_consent,
            'upload_date': app.upload_date
        })
    
    elapsed_time = (datetime.now() - start_time).total_seconds()
    
    if elapsed_time > 3:
        print(f"ВНИМАНИЕ: Время визуализации ({elapsed_time:.2f}с) превысило требуемые 3 секунды")
    
    return result


def get_program_applicants(program_code, date=None, sort_by='total_score', order='desc'):
    """
    П.12: Визуализация конкурсных списков по отдельной программе
    """
    start_time = datetime.now()
    
    if not date:
        latest = get_latest_csv()
        date = latest.replace('.csv', '') if latest else None
    
    if not date:
        return {
            'name': PROGRAMS[program_code]['name'],
            'seats': PROGRAMS[program_code]['seats'],
            'passing_score': None,
            'applicants': []
        }
    
    query = Applicant.query.filter_by(upload_date=date, program_code=program_code)
    
    # Сортировка
    if sort_by == 'total_score':
        query = query.order_by(Applicant.total_score.desc() if order == 'desc' else Applicant.total_score.asc())
    elif sort_by == 'priority':
        query = query.order_by(Applicant.priority.asc() if order == 'asc' else Applicant.priority.desc())
    
    applicants = query.all()
    
    # Получаем проходной балл
    passing_score_record = PassingScore.query.filter_by(
        program_code=program_code,
        upload_date=date
    ).first()
    
    result = {
        'name': PROGRAMS[program_code]['name'],
        'seats': PROGRAMS[program_code]['seats'],
        'passing_score': passing_score_record.passing_score if passing_score_record else None,
        'applicants': []
    }
    
    for app in applicants:
        result['applicants'].append({
            'id': app.id,
            'priority': app.priority,
            'physics_ict': app.physics_ict_score,
            'russian': app.russian_score,
            'math': app.math_score,
            'extra': app.extra_score,
            'total_score': app.total_score,
            'has_consent': app.has_consent
        })
    
    elapsed_time = (datetime.now() - start_time).total_seconds()
    
    if elapsed_time > 3:
        print(f"ВНИМАНИЕ: Время визуализации ({elapsed_time:.2f}с) превысило требуемые 3 секунды")
    
    return result


def calculate_passing_scores(date=None):
    """
    П.13: Расчет проходных баллов на каждую ОП
    
    При расчете учитываются:
    - Приоритеты ОП, выбранных абитуриентами
    - Только абитуриенты, предоставившие согласие о зачислении
    
    Возвращает словарь: {код_программы: проходной_балл или None (НЕДОБОР)}
    """
    if not date:
        latest = get_latest_csv()
        date = latest.replace('.csv', '') if latest else None
    
    if not date:
        return {}
    
    results = {}
    
    # Получаем всех абитуриентов с согласием
    all_applicants_with_consent = Applicant.query.filter_by(
        upload_date=date,
        has_consent=True
    ).order_by(Applicant.total_score.desc()).all()
    
    # Группируем по ID абитуриента для учета приоритетов
    applicants_by_id = {}
    for app in all_applicants_with_consent:
        if app.id not in applicants_by_id:
            applicants_by_id[app.id] = []
        applicants_by_id[app.id].append(app)
    
    # Сортируем заявки каждого абитуриента по приоритету
    for applicant_id in applicants_by_id:
        applicants_by_id[applicant_id].sort(key=lambda x: x.priority)
    
    # Распределяем места с учетом приоритетов
    enrolled = {code: [] for code in PROGRAMS.keys()}
    enrolled_ids = set()
    
    # Сортируем всех абитуриентов по общему баллу (по убыванию)
    sorted_applicant_ids = sorted(
        applicants_by_id.keys(),
        key=lambda x: max(app.total_score for app in applicants_by_id[x]),
        reverse=True
    )
    
    for applicant_id in sorted_applicant_ids:
        if applicant_id in enrolled_ids:
            continue
        
        # Проходим по приоритетам абитуриента
        for app in applicants_by_id[applicant_id]:
            program_code = app.program_code
            seats = PROGRAMS[program_code]['seats']
            
            if len(enrolled[program_code]) < seats:
                enrolled[program_code].append(app)
                enrolled_ids.add(applicant_id)
                break
    
    # Рассчитываем проходной балл для каждой программы
    for program_code, program_data in PROGRAMS.items():
        seats = program_data['seats']
        enrolled_list = enrolled[program_code]
        
        # Сортируем зачисленных по баллам
        enrolled_list.sort(key=lambda x: x.total_score, reverse=True)
        
        passing_score = None
        if len(enrolled_list) >= seats:
            passing_score = enrolled_list[seats - 1].total_score
        
        # Сохраняем в БД
        existing_record = PassingScore.query.filter_by(
            program_code=program_code,
            upload_date=date
        ).first()
        
        if existing_record:
            existing_record.passing_score = passing_score
            existing_record.applicants_with_consent = len(enrolled_list)
            existing_record.calculated_at = datetime.utcnow()
        else:
            new_record = PassingScore(
                program_code=program_code,
                passing_score=passing_score,
                upload_date=date,
                seats_available=seats,
                applicants_with_consent=len(enrolled_list)
            )
            db.session.add(new_record)
        
        results[program_code] = passing_score
    
    db.session.commit()
    
    return results


def get_statistics(date=None):
    """
    Возвращает общую статистику по абитуриентам
    """
    if not date:
        latest = get_latest_csv()
        date = latest.replace('.csv', '') if latest else None
    
    if not date:
        return {
            'total_applicants': 0,
            'with_consent': 0,
            'last_update': None
        }
    
    total = Applicant.query.filter_by(upload_date=date).count()
    with_consent = Applicant.query.filter_by(upload_date=date, has_consent=True).count()
    
    return {
        'total_applicants': total,
        'with_consent': with_consent,
        'last_update': date.replace('_', '.')
    }


def get_report_dates():
    """
    Возвращает список дат, по которым доступны отчеты
    """
    files = get_csv_files()
    return [f.replace('.csv', '').replace('_', '.') for f in files]


def generate_pdf_report(date):
    """
    П.14: Формирование PDF отчета
    
    Отчет содержит:
    a. Дата и время формирования отчета
    b. Проходные баллы на ОП (или НЕДОБОР)
    c. Динамика проходного балла на ОП по всем дням в виде графиков (за 4 дня)
    d. Списки абитуриентов, которые будут зачислены на каждую ОП
    e. Статистику по каждой ОП в виде таблицы
    """
    safe_date = date.replace('.', '_')
    
    # Регистрируем шрифт для поддержки кириллицы
    try:
        pdfmetrics.registerFont(TTFont('DejaVu', 'DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont('DejaVu-Bold', 'DejaVuSans-Bold.ttf'))
    except:
        # Если шрифты не найдены, используем стандартные
        pass
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    story = []
    
    styles = getSampleStyleSheet()
    
    # Создаем кастомные стили
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#1a237e'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='DejaVu-Bold' if 'DejaVu-Bold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#283593'),
        spaceAfter=12,
        fontName='DejaVu-Bold' if 'DejaVu-Bold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'
    )
    
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=10,
        fontName='DejaVu' if 'DejaVu' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'
    )
    
    # П.14.a: Заголовок с датой и временем
    title_text = f"Отчет по конкурсным спискам абитуриентов<br/>на {date}"
    story.append(Paragraph(title_text, title_style))
    
    generation_time = datetime.now().strftime('%d.%m.%Y %H:%M:%S')
    story.append(Paragraph(f"Дата и время формирования отчета: {generation_time}", normal_style))
    story.append(Spacer(1, 20))
    
    # П.14.b: Проходные баллы
    story.append(Paragraph("Проходные баллы по образовательным программам", heading_style))
    
    passing_scores_data = [['Программа', 'Мест', 'Проходной балл']]
    for code, program in PROGRAMS.items():
        ps_record = PassingScore.query.filter_by(
            program_code=code,
            upload_date=safe_date
        ).first()
        
        score_text = str(ps_record.passing_score) if ps_record and ps_record.passing_score else 'НЕДОБОР'
        passing_scores_data.append([
            program['name'],
            str(program['seats']),
            score_text
        ])
    
    passing_table = Table(passing_scores_data, colWidths=[300, 60, 100])
    passing_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3f51b5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'DejaVu-Bold' if 'DejaVu-Bold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#e8eaf6')),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTNAME', (0, 1), (-1, -1), 'DejaVu' if 'DejaVu' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'),
    ]))
    story.append(passing_table)
    story.append(Spacer(1, 30))
    
    # П.14.c: Динамика проходных баллов (графики)
    story.append(Paragraph("Динамика проходных баллов", heading_style))
    
    # Получаем данные по всем датам
    all_dates = get_report_dates()
    dynamics_data = {code: [] for code in PROGRAMS.keys()}
    date_labels = []
    
    for report_date in all_dates:
        safe_report_date = report_date.replace('.', '_')
        date_labels.append(report_date)
        
        for code in PROGRAMS.keys():
            ps_record = PassingScore.query.filter_by(
                program_code=code,
                upload_date=safe_report_date
            ).first()
            
            score = ps_record.passing_score if ps_record and ps_record.passing_score else 0
            dynamics_data[code].append(score)
    
    # Создаем график
    plt.figure(figsize=(10, 6))
    
    for code, program in PROGRAMS.items():
        if dynamics_data[code]:
            plt.plot(date_labels, dynamics_data[code], marker='o', label=program['name'], linewidth=2)
    
    plt.xlabel('Дата', fontsize=12)
    plt.ylabel('Проходной балл', fontsize=12)
    plt.title('Динамика проходных баллов по образовательным программам', fontsize=14, fontweight='bold')
    plt.legend(loc='best', fontsize=10)
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    # Сохраняем график в буфер
    graph_buffer = BytesIO()
    plt.savefig(graph_buffer, format='png', dpi=150, bbox_inches='tight')
    graph_buffer.seek(0)
    plt.close()
    
    # Добавляем график в PDF
    img = Image(graph_buffer, width=500, height=300)
    story.append(img)
    story.append(Spacer(1, 20))
    story.append(PageBreak())
    
    # П.14.d: Списки зачисленных абитуриентов
    story.append(Paragraph("Списки зачисленных абитуриентов", heading_style))
    
    for code, program in PROGRAMS.items():
        story.append(Paragraph(f"{program['name']} ({program['seats']} мест)", heading_style))
        
        # Получаем зачисленных
        enrolled = get_enrolled_applicants(code, safe_date, program['seats'])
        
        if enrolled:
            enrolled_data = [['№', 'ID абитуриента', 'Сумма баллов', 'Приоритет']]
            for idx, app in enumerate(enrolled, 1):
                enrolled_data.append([
                    str(idx),
                    str(app.id),
                    str(app.total_score),
                    str(app.priority)
                ])
            
            enrolled_table = Table(enrolled_data, colWidths=[40, 120, 120, 100])
            enrolled_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#5c6bc0')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'DejaVu-Bold' if 'DejaVu-Bold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTNAME', (0, 1), (-1, -1), 'DejaVu' if 'DejaVu' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'),
            ]))
            story.append(enrolled_table)
        else:
            story.append(Paragraph("Нет зачисленных абитуриентов", normal_style))
        
        story.append(Spacer(1, 20))
    
    story.append(PageBreak())
    
    # П.14.e: Статистика по каждой ОП
    story.append(Paragraph("Статистика по образовательным программам", heading_style))
    
    stats_data = [['Программа', 'Всего заявок', 'С согласием', 'Зачислено', 'Конкурс']]
    
    for code, program in PROGRAMS.items():
        total_apps = Applicant.query.filter_by(
            upload_date=safe_date,
            program_code=code
        ).count()
        
        with_consent = Applicant.query.filter_by(
            upload_date=safe_date,
            program_code=code,
            has_consent=True
        ).count()
        
        enrolled_count = len(get_enrolled_applicants(code, safe_date, program['seats']))
        
        competition = round(total_apps / program['seats'], 2) if program['seats'] > 0 else 0
        
        stats_data.append([
            program['name'],
            str(total_apps),
            str(with_consent),
            str(enrolled_count),
            str(competition)
        ])
    
    stats_table = Table(stats_data, colWidths=[200, 80, 80, 80, 60])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3f51b5')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'DejaVu-Bold' if 'DejaVu-Bold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#e8eaf6')),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('FONTNAME', (0, 1), (-1, -1), 'DejaVu' if 'DejaVu' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'),
    ]))
    story.append(stats_table)
    
    # Генерируем PDF
    doc.build(story)
    buffer.seek(0)
    
    return buffer


def get_enrolled_applicants(program_code, date, seats):
    """
    Возвращает список зачисленных абитуриентов на программу
    с учетом приоритетов
    """
    # Получаем всех абитуриентов с согласием
    all_applicants_with_consent = Applicant.query.filter_by(
        upload_date=date,
        has_consent=True
    ).order_by(Applicant.total_score.desc()).all()
    
    # Группируем по ID
    applicants_by_id = {}
    for app in all_applicants_with_consent:
        if app.id not in applicants_by_id:
            applicants_by_id[app.id] = []
        applicants_by_id[app.id].append(app)
    
    # Сортируем по приоритету для каждого абитуриента
    for applicant_id in applicants_by_id:
        applicants_by_id[applicant_id].sort(key=lambda x: x.priority)
    
    # Распределяем места
    enrolled = {code: [] for code in PROGRAMS.keys()}
    enrolled_ids = set()
    
    sorted_applicant_ids = sorted(
        applicants_by_id.keys(),
        key=lambda x: max(app.total_score for app in applicants_by_id[x]),
        reverse=True
    )
    
    for applicant_id in sorted_applicant_ids:
        if applicant_id in enrolled_ids:
            continue
        
        for app in applicants_by_id[applicant_id]:
            prog_code = app.program_code
            prog_seats = PROGRAMS[prog_code]['seats']
            
            if len(enrolled[prog_code]) < prog_seats:
                enrolled[prog_code].append(app)
                enrolled_ids.add(applicant_id)
                break
    
    # Возвращаем зачисленных на конкретную программу
    return enrolled[program_code]
