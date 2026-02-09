from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()


class Applicant(db.Model):
    __tablename__ = 'applicants'
    __table_args__ = (
        db.PrimaryKeyConstraint('id', 'upload_date'),
    )

    id = db.Column(db.Integer, nullable=False)  # id из CSV
    upload_date = db.Column(db.String(20), nullable=False, index=True)
    program_code = db.Column(db.String(10), nullable=False, index=True)
    priority = db.Column(db.Integer, nullable=False)
    physics_ict_score = db.Column(db.Integer, nullable=False)
    russian_score = db.Column(db.Integer, nullable=False)
    math_score = db.Column(db.Integer, nullable=False)
    extra_score = db.Column(db.Integer, nullable=False)
    total_score = db.Column(db.Integer, nullable=False)
    has_consent = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    
    def __repr__(self):
        return f'<Applicant {self.id} - {self.program_code}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'program_code': self.program_code,
            'priority': self.priority,
            'physics_ict_score': self.physics_ict_score,
            'russian_score': self.russian_score,
            'math_score': self.math_score,
            'extra_score': self.extra_score,
            'total_score': self.total_score,
            'has_consent': self.has_consent,
            'upload_date': self.upload_date
        }


class PassingScore(db.Model):
    """
    Модель для хранения проходных баллов по программам на определенную дату
    """
    __tablename__ = 'passing_scores'
    
    id = db.Column(db.Integer, primary_key=True)
    program_code = db.Column(db.String(10), nullable=False, index=True)
    passing_score = db.Column(db.Integer, nullable=True)  # None означает НЕДОБОР
    upload_date = db.Column(db.String(20), nullable=False, index=True)
    seats_available = db.Column(db.Integer, nullable=False)
    applicants_with_consent = db.Column(db.Integer, nullable=False)
    calculated_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PassingScore {self.program_code} - {self.upload_date}: {self.passing_score}>'
