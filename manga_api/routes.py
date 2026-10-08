from datetime import datetime

from flask import Blueprint, jsonify, request

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


@api.route('/api/bookmark', methods=['GET'])
def get_bookmarks():
    return jsonify({
        'status': 'success',
        'data': [],
    }), 200


@api.route('/api', methods=['GET'])
@api.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'API running'}), 200
