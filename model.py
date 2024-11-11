from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255))
    pref_project = db.Column(db.String(15))
    pref_language = db.Column(db.String(4))
    user_language = db.Column(db.String(4), default='en')
    skip_upload_selection = db.Column(db.Boolean, default=False)

    def __repr__(self):
        return '<User %r>' % self.username