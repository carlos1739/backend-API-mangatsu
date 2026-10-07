from datetime import datetime

from . import db


class Manga(db.Model):
    __tablename__ = 'manga'

    id = db.Column(db.Integer, primary_key=True)
    mal_id = db.Column(db.Integer, unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    author = db.Column(db.String(255))
    chapter = db.Column(db.String(50))
    status = db.Column(db.String(50))
    sinopsis = db.Column(db.Text)
    release = db.Column(db.String(10))
    genre = db.Column(db.String(500))
    rating = db.Column(db.Float, default=0.0)
    link_gambar = db.Column(db.String(500))
    likes = db.Column(db.Integer, default=0)
    views = db.Column(db.Integer, default=0)
    cached_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.mal_id,
            'title': self.title,
            'author': self.author,
            'chapter': self.chapter,
            'status': self.status,
            'sinopsis': self.sinopsis,
            'release': self.release,
            'genre': [genre for genre in self.genre.split(',') if genre] if self.genre else [],
            'rating': self.rating or 0.0,
            'linkGambar': self.link_gambar,
            'likes': self.likes or 0,
            'view': self.views or 0,
        }


class Bookmark(db.Model):
    __tablename__ = 'bookmarks'

    id = db.Column(db.Integer, primary_key=True)
    manga_id = db.Column(db.Integer, nullable=False, unique=True)
    title = db.Column(db.String(255), nullable=False)
    image_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'manga_id': self.manga_id,
            'title': self.title,
            'image_url': self.image_url,
            'created_at': self.created_at.isoformat(),
        }
