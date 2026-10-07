import os
from manga_api import app, db
from manga_api.models import Bookmark, Manga


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    print('\n=== Available Routes ===')
    for rule in app.url_map.iter_rules():
        print(f'{rule.endpoint}: {rule.rule}')
    print('=======================\n')

    app.run(host='0.0.0.0', port=5000, debug=os.getenv('FLASK_DEBUG', '1') == '1')