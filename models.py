from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Visitor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(200))
    timestamp = db.Column(db.String(100))
    face_match_status = db.Column(db.String(50))
    image_path = db.Column(db.String(300))

    def __repr__(self):
        return f"<Visitor {self.student_id} - {self.name}>"
