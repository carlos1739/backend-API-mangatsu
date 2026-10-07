from datetime import datetime

from flask import Blueprint, jsonify, request

from . import db
from .models import Bookmark, Manga
from .services import (
    LIST_CACHE,
    fetch_tenrai,
    is_fresh,
    manga_by_ids,
    parse_tenrai_response,
    save_many,
    upsert_manga,
)


api = Blueprint('api', __name__)


def ok_list(mangas, source, **extra):
    return ok_list_data([manga.to_dict() for manga in mangas], source, **extra)


def ok_list_data(data, source, **extra):
    return jsonify({
        'status': 'success',
        'source': source,
        'data': data,
        **extra,
    }), 200


def serve_list(cache_key, path, params, db_fallback=None, **extra):
    entry = LIST_CACHE.get(cache_key)
    ids = entry[1] if entry else []

    if entry and is_fresh(entry[0]):
        if len(entry) > 2:
            return ok_list_data(entry[2], 'cache', **extra)
        mangas = manga_by_ids(ids)
        if mangas:
            return ok_list(mangas, 'cache', **extra)

    data, error = fetch_tenrai(path, params)
    if error:
        mangas = manga_by_ids(ids)
        if not mangas and db_fallback:
            mangas = db_fallback()
        if mangas:
            return ok_list(mangas, 'stale-cache', **extra)
        return jsonify({'status': 'error', 'message': error[0]}), error[1]

    mangas = save_many(data.get('data', []))
    LIST_CACHE[cache_key] = (
        datetime.utcnow(),
        [manga.mal_id for manga in mangas],
        [manga.to_dict() for manga in mangas],
    )
    return ok_list(mangas, 'tenrai', **extra)


@api.route('/api/manga', methods=['GET'])
def get_all_manga():
    try:
        page = max(request.args.get('page', 1, type=int), 1)

        def fallback():
            return Manga.query.order_by(Manga.rating.desc()).limit(25).all()

        return serve_list(
            f'top:{page}',
            '/top/manga',
            {'limit': 25, 'page': page},
            db_fallback=fallback if page == 1 else None,
            page=page,
        )
    except Exception as error:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(error)}), 500


@api.route('/api/manga/search', methods=['GET'])
def search_manga():
    try:
        query = request.args.get('q', '').strip()
        page = max(request.args.get('page', 1, type=int), 1)
        if not query:
            return jsonify({'status': 'success', 'data': []}), 200

        def fallback():
            return Manga.query.filter(
                Manga.title.ilike(f'%{query}%') |
                Manga.author.ilike(f'%{query}%')
            ).limit(20).all()

        return serve_list(
            f'search:{query.lower()}:{page}',
            '/manga',
            {'q': query, 'limit': 20, 'page': page},
            db_fallback=fallback,
            page=page,
        )
    except Exception as error:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(error)}), 500


@api.route('/api/manga/<int:id>', methods=['GET'])
def get_manga_detail(id):
    try:
        manga = Manga.query.filter_by(mal_id=id).first()
        if manga and is_fresh(manga.cached_at):
            return jsonify({
                'status': 'success',
                'source': 'cache',
                'data': manga.to_dict(),
            }), 200

        data, error = fetch_tenrai(f'/manga/{id}/full')
        if error:
            if manga:
                return jsonify({
                    'status': 'success',
                    'source': 'stale-cache',
                    'data': manga.to_dict(),
                }), 200
            return jsonify({'status': 'error', 'message': error[0]}), error[1]

        parsed = parse_tenrai_response(data.get('data') or {})
        if not parsed:
            return jsonify({'status': 'error', 'message': 'Manga not found'}), 404

        manga = upsert_manga(parsed)
        db.session.commit()
        return jsonify({
            'status': 'success',
            'source': 'tenrai',
            'data': manga.to_dict(),
        }), 200
    except Exception as error:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(error)}), 500


@api.route('/api/manga/genre/<int:genre_id>', methods=['GET'])
def get_by_genre(genre_id):
    try:
        page = max(request.args.get('page', 1, type=int), 1)
        return serve_list(
            f'genre:{genre_id}:{page}',
            '/manga',
            {'genres': genre_id, 'limit': 25, 'page': page},
            page=page,
        )
    except Exception as error:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(error)}), 500


@api.route('/api/bookmark', methods=['POST'])
def add_bookmark():
    try:
        data = request.get_json(silent=True) or {}
        if not data.get('manga_id') or not data.get('title'):
            return jsonify({
                'status': 'error',
                'message': 'manga_id dan title wajib diisi',
            }), 400

        existing = Bookmark.query.filter_by(manga_id=data['manga_id']).first()
        if existing:
            return jsonify({'status': 'error', 'message': 'Already bookmarked'}), 400

        bookmark = Bookmark(
            manga_id=data['manga_id'],
            title=data['title'],
            image_url=data.get('image_url'),
        )
        db.session.add(bookmark)
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Bookmark added',
            'data': bookmark.to_dict(),
        }), 201
    except Exception as error:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(error)}), 400


@api.route('/api/bookmark', methods=['GET'])
def get_bookmarks():
    try:
        bookmarks = Bookmark.query.all()
        return jsonify({
            'status': 'success',
            'data': [bookmark.to_dict() for bookmark in bookmarks],
        }), 200
    except Exception as error:
        return jsonify({'status': 'error', 'message': str(error)}), 500


@api.route('/api/bookmark/<int:manga_id>', methods=['GET'])
def check_bookmark(manga_id):
    try:
        bookmark = Bookmark.query.filter_by(manga_id=manga_id).first()
        if bookmark:
            return jsonify({
                'status': 'success',
                'isBookmarked': True,
                'data': bookmark.to_dict(),
            }), 200
        return jsonify({'status': 'success', 'isBookmarked': False}), 200
    except Exception as error:
        return jsonify({'status': 'error', 'message': str(error)}), 500


@api.route('/api/bookmark/<int:manga_id>', methods=['DELETE'])
def delete_bookmark(manga_id):
    try:
        bookmark = Bookmark.query.filter_by(manga_id=manga_id).first()
        if not bookmark:
            return jsonify({'status': 'error', 'message': 'Not bookmarked'}), 404

        db.session.delete(bookmark)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Bookmark removed'}), 200
    except Exception as error:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(error)}), 500


@api.route('/api', methods=['GET'])
@api.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'API running'}), 200
