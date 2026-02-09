from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from config import Config
from models import db
from services import (
    get_all_applicants,
    get_program_applicants,
    calculate_passing_scores,
    upload_competition_list,
    get_statistics,
    get_report_dates,
    generate_pdf_report,
    get_csv_files,
    PROGRAMS
)
import os


def create_app(config_class=Config):
    """
    Фабрика приложений Flask
    """
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Инициализация базы данных
    db.init_app(app)
    
    # Создание таблиц БД
    with app.app_context():
        db.create_all()
        
        # Создание необходимых директорий
        if not os.path.exists(app.config['DATA_DIR']):
            os.makedirs(app.config['DATA_DIR'])
        if not os.path.exists(app.config['REPORTS_DIR']):
            os.makedirs(app.config['REPORTS_DIR'])
    
    return app


app = create_app()


@app.route("/", methods=["GET"])
def index():
    """
    П.12: Главная страница с визуализацией конкурсных списков
    
    Отображает:
    - Единый список всех абитуриентов с каскадом приоритетов
    - Возможности сортировки и фильтрации
    - Время перестроения не должно превышать 3 секунды
    """
    selected_file = request.args.get("file")
    sort_by = request.args.get("sort_by", "total_score")
    order = request.args.get("order", "desc")
    program_filter = request.args.get("program_filter", "all")
    
    files = get_csv_files()
    if selected_file not in [f.replace('.csv', '').replace('_', '.') for f in files]:
        latest_file = files[-1].replace('.csv', '').replace('_', '.') if files else None
        selected_file = latest_file
    
    safe_date = selected_file.replace('.', '_') if selected_file else None
    
    # Получаем всех абитуриентов
    applicants = get_all_applicants(safe_date, sort_by, order)
    
    # Фильтрация по программе
    if program_filter != "all":
        applicants = [a for a in applicants if a['program_code'] == program_filter]
    
    stats = get_statistics(safe_date)
    
    # Форматируем список файлов для отображения
    formatted_files = [f.replace('.csv', '').replace('_', '.') for f in files]
    
    return render_template(
        "index.html",
        applicants=applicants,
        total_applicants=stats["total_applicants"],
        with_consent=stats["with_consent"],
        last_update=stats["last_update"],
        files=formatted_files,
        selected_file=selected_file,
        sort_by=sort_by,
        order=order,
        program_filter=program_filter,
        programs=PROGRAMS
    )


@app.route("/program/<code>", methods=["GET"])
def program_page(code):
    """
    П.12: Страница конкретной образовательной программы
    
    Отображает:
    - Список абитуриентов по программе
    - Проходной балл
    - Количество мест
    - Возможности сортировки
    """
    if code not in PROGRAMS:
        flash("Неверный код программы", "error")
        return redirect(url_for("index"))
    
    selected_file = request.args.get("file")
    sort_by = request.args.get("sort_by", "total_score")
    order = request.args.get("order", "desc")
    
    files = get_csv_files()
    if selected_file not in [f.replace('.csv', '').replace('_', '.') for f in files]:
        latest_file = files[-1].replace('.csv', '').replace('_', '.') if files else None
        selected_file = latest_file
    
    safe_date = selected_file.replace('.', '_') if selected_file else None
    
    program_data = get_program_applicants(code, safe_date, sort_by, order)
    
    formatted_files = [f.replace('.csv', '').replace('_', '.') for f in files]
    
    return render_template(
        "program.html",
        program_code=code,
        program_name=program_data["name"],
        seats=program_data["seats"],
        passing_score=program_data["passing_score"],
        applicants=program_data["applicants"],
        files=formatted_files,
        selected_file=selected_file,
        sort_by=sort_by,
        order=order
    )


@app.route("/upload", methods=["POST"])
def upload():
    """
    П.2-4: Загрузка конкурсных списков в БД
    
    Обеспечивает:
    - Загрузку CSV файлов
    - Обновление БД (удаление, добавление, обновление записей)
    - Время загрузки не более 5 секунд
    """
    file = request.files.get("file")
    date = request.form.get("date")
    
    if not file or not date:
        flash("Файл или дата не указаны", "error")
        return redirect(url_for("index"))
    
    if not file.filename.lower().endswith(".csv"):
        flash("Можно загружать только CSV файлы", "error")
        return redirect(url_for("index"))
    
    try:
        upload_competition_list(file, date)
    except Exception as e:
        flash(f"Ошибка при загрузке: {str(e)}", "error")
    
    return redirect(url_for("index"))


@app.route("/calculate", methods=["POST"])
def calculate():
    """
    П.13: Расчет проходных баллов
    
    Рассчитывает проходной балл для каждой ОП с учетом:
    - Приоритетов абитуриентов
    - Только абитуриентов с согласием
    
    Отображает результаты в графическом интерфейсе
    """
    selected_file = request.form.get("file")
    
    files = get_csv_files()
    if selected_file not in [f.replace('.csv', '').replace('_', '.') for f in files]:
        latest_file = files[-1].replace('.csv', '').replace('_', '.') if files else None
        selected_file = latest_file
    
    safe_date = selected_file.replace('.', '_') if selected_file else None
    
    try:
        results = calculate_passing_scores(safe_date)
        msg_list = []
        
        for code, score in results.items():
            program_name = PROGRAMS[code]["name"]
            score_text = f"{score}" if score else "НЕДОБОР"
            msg_list.append(f"{program_name}: {score_text}")
        
        flash("Проходные баллы рассчитаны:<br>" + "<br>".join(msg_list), "success")
    except Exception as e:
        flash(f"Ошибка при расчете: {str(e)}", "error")
    
    return redirect(url_for("index", file=selected_file))


@app.route("/reports")
def reports():
    """
    Страница со списком доступных отчетов
    """
    dates = get_report_dates()
    return render_template("reports.html", dates=dates)


@app.route("/reports/<date>")
def report_pdf(date):
    """
    П.14: Генерация PDF отчета
    
    Формирует отчет содержащий:
    a. Дату и время формирования
    b. Проходные баллы (или НЕДОБОР)
    c. Динамику проходного балла (графики за 4 дня)
    d. Списки зачисленных абитуриентов (4 списка)
    e. Статистику по каждой ОП (таблица)
    """
    try:
        pdf_buffer = generate_pdf_report(date)
        return send_file(
            pdf_buffer,
            as_attachment=True,
            download_name=f"report_{date.replace('.', '_')}.pdf",
            mimetype='application/pdf'
        )
    except Exception as e:
        flash(f"Ошибка при генерации отчета: {str(e)}", "error")
        return redirect(url_for("reports"))


@app.route("/delete_date/<date>", methods=["POST"])
def delete_date(date):
    """
    Удаление данных за конкретную дату
    """
    try:
        safe_date = date.replace('.', '_')
        
        # Удаляем из БД
        from models import Applicant, PassingScore
        Applicant.query.filter_by(upload_date=safe_date).delete()
        PassingScore.query.filter_by(upload_date=safe_date).delete()
        db.session.commit()
        
        # Удаляем CSV файл
        csv_path = os.path.join(app.config['DATA_DIR'], f"{safe_date}.csv")
        if os.path.exists(csv_path):
            os.remove(csv_path)
        
        flash(f"Данные за {date} успешно удалены", "success")
    except Exception as e:
        flash(f"Ошибка при удалении: {str(e)}", "error")
    
    return redirect(url_for("index"))


@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5001)
