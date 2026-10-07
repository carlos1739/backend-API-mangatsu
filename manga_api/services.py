import os
from datetime import datetime, timedelta

import requests

from . import db
from .models import Manga


TENRAI_API = os.getenv('TENRAI_API', 'https://api.tenrai.org/v1').rstrip('/')
CACHE_HOURS = 24
TENRAI_TIMEOUT = (5, 10)
LIST_CACHE = {}


def create_http_session():
    return requests.Session()


HTTP_SESSION = create_http_session()


def fetch_tenrai(path, params=None):
    try:
        response = HTTP_SESSION.get(f'{TENRAI_API}{path}', params=params, timeout=TENRAI_TIMEOUT)
        if response.status_code == 200:
            return response.json(), None
        if response.status_code == 404:
            return None, ('Data tidak ditemukan di tenrai', 404)
        if response.status_code == 429:
            return None, ('Rate limit tenrai, coba lagi sebentar', 429)
        return None, (f'tenrai error {response.status_code}', 502)
    except requests.exceptions.Timeout:
        return None, ('tenrai timeout', 504)
    except requests.exceptions.RequestException as error:
        return None, (f'Tidak bisa terhubung ke tenrai: {error}', 503)
    except ValueError:
        return None, ('Respons tenrai bukan JSON yang valid', 502)


def parse_tenrai_response(item):
    mal_id = item.get('mal_id')
    if not mal_id:
        return None

    authors = item.get('authors') or []
    author = (authors[0].get('name') if authors else None) or 'Unknown'
    chapters = item.get('chapters')
    year = item.get('year')
    score = item.get('score')
    jpg = ((item.get('images') or {}).get('jpg')) or {}

    return {
        'mal_id': mal_id,
        'title': (item.get('title') or 'Unknown')[:255],
        'author': author[:255],
        'chapter': str(chapters) if chapters is not None else 'N/A',
        'status': (item.get('status') or 'Unknown')[:50],
        'sinopsis': item.get('synopsis') or '',
        'release': str(year) if year else 'Unknown',
        'genre': ','.join(genre.get('name', '') for genre in (item.get('genres') or []))[:500],
        'rating': float(score) if score else 0.0,
        'link_gambar': (jpg.get('image_url') or '')[:500],
    }


def upsert_manga(parsed):
    manga = Manga.query.filter_by(mal_id=parsed['mal_id']).first()
    if manga:
        for field in ('title', 'author', 'chapter', 'status', 'sinopsis', 'release', 'genre', 'rating', 'link_gambar'):
            setattr(manga, field, parsed[field])
        manga.cached_at = datetime.utcnow()
    else:
        manga = Manga(**parsed, likes=0, views=0)
        db.session.add(manga)
    return manga


def save_many(items):
    seen = set()
    result = []
    try:
        parsed_items = []
        for item in items:
            parsed = parse_tenrai_response(item)
            if not parsed or parsed['mal_id'] in seen:
                continue
            seen.add(parsed['mal_id'])
            parsed_items.append(parsed)

        if not parsed_items:
            return result

        ids = [parsed['mal_id'] for parsed in parsed_items]
        existing = Manga.query.filter(Manga.mal_id.in_(ids)).all()
        by_id = {manga.mal_id: manga for manga in existing}
        for parsed in parsed_items:
            manga = by_id.get(parsed['mal_id'])
            if manga is None:
                manga = Manga(**parsed, likes=0, views=0)
                db.session.add(manga)
            else:
                for field in ('title', 'author', 'chapter', 'status', 'sinopsis', 'release', 'genre', 'rating', 'link_gambar'):
                    setattr(manga, field, parsed[field])
                manga.cached_at = datetime.utcnow()
            result.append(manga)
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return result


def is_fresh(timestamp):
    return datetime.utcnow() - timestamp < timedelta(hours=CACHE_HOURS)


def manga_by_ids(ids):
    if not ids:
        return []
    rows = Manga.query.filter(Manga.mal_id.in_(ids)).all()
    by_id = {manga.mal_id: manga for manga in rows}
    return [by_id[mal_id] for mal_id in ids if mal_id in by_id]
