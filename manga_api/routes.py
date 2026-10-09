from datetime import datetime

from flask import Blueprint, jsonify, request

from database.db import execute_query, execute_write

from .services import (
    LIST_CACHE,
    fetch_tenrai,
    is_fresh,
    parse_tenrai_response,
    save_many,
)

api = Blueprint('api', __name__)

def ok_list(data, source, **extra):
    return jsonify({
        'status': 'success',
        'source': source,
        'data': data,
        **extra,
    }), 200

def serve_list(cache_key, path, params, **extra):
    entry = LIST_CACHE.get(cache_key)
    if entry and is_fresh(entry[0]):
        return ok_list(entry[2], 'cache', **extra)

    data, error = fetch_tenrai(path, params)
    if error:
        return jsonify({'status': 'error', 'message': error[0]}), error[1]

    mangas = save_many(data.get('data', []))
    LIST_CACHE[cache_key] = (
        datetime.utcnow(),
        [manga['mal_id'] for manga in mangas],
        mangas,
    )
    return ok_list(mangas, 'tenrai', **extra)

@api.route('/api/manga', methods=['GET'])
def get_all_manga():
    page = max(request.args.get('page', 1, type=int), 1)
    return serve_list(
        f'top:{page}',
        '/top/manga',
        {'limit': 25, 'page': page},
        page=page,
    )

@api.route('/api/manga/search', methods=['GET'])
def search_manga():
    query = request.args.get('q', '').strip()
    page = max(request.args.get('page', 1, type=int), 1)
    if not query:
        return jsonify({'status': 'success', 'data': []}), 200

    return serve_list(
        f'search:{query.lower()}:{page}',
        '/manga',
        {'q': query, 'limit': 20, 'page': page},
        page=page,
    )

@api.route('/api/manga/<int:id>', methods=['GET'])
def get_manga_detail(id):
    cached = LIST_CACHE.get('manga-detail', {}).get(id)
    if cached and is_fresh(cached['cached_at']):
        return jsonify({
            'status': 'success',
            'source': 'cache',
            'data': cached,
        }), 200

    data, error = fetch_tenrai(f'/manga/{id}/full')
    if error:
        return jsonify({'status': 'error', 'message': error[0]}), error[1]

    parsed = parse_tenrai_response(data.get('data') or {})
    if not parsed:
        return jsonify({'status': 'error', 'message': 'Manga not found'}), 404

    parsed['cached_at'] = datetime.utcnow()
    LIST_CACHE['manga-detail'] = {id: parsed}
    return jsonify({
        'status': 'success',
        'source': 'tenrai',
        'data': parsed,
    }), 200

@api.route('/api/manga/genre/<int:genre_id>', methods=['GET'])
def get_by_genre(genre_id):
    page = max(request.args.get('page', 1, type=int), 1)
    return serve_list(
        f'genre:{genre_id}:{page}',
        '/manga',
        {'genres': genre_id, 'limit': 25, 'page': page},
        page=page,
    )

# seluruh fitur bookmark per user
VALID_READ_STATUS = ('reading', 'plan', 'completed')

def get_user_id():
    """Ambil user_id dari query string (?user_id=) atau body JSON."""
    data = request.get_json(silent=True) or {}
    raw = request.args.get('user_id') or data.get('user_id')
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None

# Ambil semua bookmark milik user (dipakai halaman Rak Buku)
@api.route('/api/bookmark', methods=['GET'])
def get_bookmarks():
    user_id = get_user_id()
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Login dulu'}), 401

    rows = execute_query(
        "SELECT manga_id AS mal_id, title, image_url AS link_gambar, read_status "
        "FROM bookmarks WHERE user_id = %s ORDER BY created_at DESC",
        (user_id,),
    )
    for row in rows:
        row['bookmark'] = True
    return jsonify({'status': 'success', 'data': rows}), 200

# Simpan bookmark (kalau sudah ada, judul dan gambar diperbarui; status tidak diubah)
@api.route('/api/bookmark', methods=['POST'])
def add_bookmark():
    data = request.get_json(silent=True) or {}
    user_id = get_user_id()
    manga_id = data.get('manga_id')
    if not user_id or not manga_id:
        return jsonify({'status': 'error', 'message': 'user_id dan manga_id wajib'}), 400

    execute_write(
        "INSERT INTO bookmarks (user_id, manga_id, title, image_url) "
        "VALUES (%s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE title = VALUES(title), image_url = VALUES(image_url)",
        (user_id, manga_id, (data.get('title') or '')[:255], (data.get('image_url') or '')[:500]),
    )
    return jsonify({'status': 'success', 'message': 'Bookmark disimpan'}), 201

# Cek satu manga: sudah di-bookmark atau belum, dan apa statusnya
@api.route('/api/bookmark/<int:manga_id>', methods=['GET'])
def is_bookmarked(manga_id):
    user_id = get_user_id()
    if not user_id:
        return jsonify({'status': 'success', 'isBookmarked': False}), 200

    rows = execute_query(
        "SELECT read_status FROM bookmarks WHERE user_id = %s AND manga_id = %s LIMIT 1",
        (user_id, manga_id),
    )
    return jsonify({
        'status': 'success',
        'isBookmarked': bool(rows),
        'readStatus': rows[0]['read_status'] if rows else None,
    }), 200

# UPDATE: ubah status baca bookmark
@api.route('/api/bookmark/<int:manga_id>', methods=['PUT'])
def update_bookmark(manga_id):
    data = request.get_json(silent=True) or {}
    user_id = get_user_id()
    read_status = data.get('read_status')
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Login dulu'}), 401
    if read_status not in VALID_READ_STATUS:
        return jsonify({'status': 'error', 'message': 'Status tidak valid'}), 400

    exists = execute_query(
        "SELECT id FROM bookmarks WHERE user_id = %s AND manga_id = %s LIMIT 1",
        (user_id, manga_id),
    )
    if not exists:
        return jsonify({'status': 'error', 'message': 'Bookmark tidak ditemukan'}), 404

    execute_write(
        "UPDATE bookmarks SET read_status = %s WHERE user_id = %s AND manga_id = %s",
        (read_status, user_id, manga_id),
    )
    return jsonify({'status': 'success', 'message': 'Status diperbarui'}), 200

# DELETE: hapus bookmark
@api.route('/api/bookmark/<int:manga_id>', methods=['DELETE'])
def remove_bookmark(manga_id):
    user_id = get_user_id()
    if not user_id:
        return jsonify({'status': 'error', 'message': 'Login dulu'}), 401

    execute_write(
        "DELETE FROM bookmarks WHERE user_id = %s AND manga_id = %s",
        (user_id, manga_id),
    )
    return jsonify({'status': 'success', 'message': 'Bookmark dihapus'}), 200

@api.route('/api', methods=['GET'])
@api.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'API running'}), 200