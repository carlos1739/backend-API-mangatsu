import os
from datetime import datetime, timedelta

import requests


TENRAI_API = os.getenv('TENRAI_API', 'https://api.tenrai.org/v1').rstrip('/')
CACHE_HOURS = 24
TENRAI_TIMEOUT = (5, 10)
LIST_CACHE = {}


def create_http_session():
    return requests.Session()


HTTP_SESSION = create_http_session()


def fetch_tenrai(path, params=None):
    try:
        response = HTTP_SESSION.get(
            f'{TENRAI_API}{path}',
            params=params,
            timeout=TENRAI_TIMEOUT,
        )
        if response.status_code == 200:
            return response.json(), None
        if response.status_code == 404:
            return None, ('Data tidak ditemukan di tenrai', 404)
        if response.status_code == 429:
            return None, ('Rate limit tenrai, coba lagi sebentar', 429)
        return None, (f'Tenrai error {response.status_code}', 502)
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
    jpg = (item.get('images') or {}).get('jpg') or {}

    return {
        'mal_id': mal_id,
        'title': (item.get('title') or 'Unknown')[:255],
        'author': author[:255],
        'chapter': str(item.get('chapters')) if item.get('chapters') is not None else 'N/A',
        'status': (item.get('status') or 'Unknown')[:50],
        'synopsis': item.get('synopsis') or '',
        'release': str(item.get('year')) if item.get('year') else 'Unknown',
        'genre': ','.join(
            genre.get('name', '') for genre in (item.get('genres') or [])
        )[:500],
        'rating': float(item.get('score')) if item.get('score') else 0.0,
        'link_gambar': (jpg.get('image_url') or '')[:500],
    }


def save_many(items):
    result = []
    seen = set()
    for item in items:
        parsed = parse_tenrai_response(item)
        if parsed and parsed['mal_id'] not in seen:
            seen.add(parsed['mal_id'])
            result.append(parsed)
    return result


def is_fresh(timestamp):
    return datetime.utcnow() - timestamp < timedelta(hours=CACHE_HOURS)


def manga_by_ids(ids):
    if not ids:
        return []
    return [item for item in LIST_CACHE.get('manga-by-id', []) if item['mal_id'] in ids]


def upsert_manga(parsed):
    return parsed
