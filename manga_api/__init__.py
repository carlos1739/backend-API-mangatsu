import os

from flask import Flask
from flask_cors import CORS


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'development-only')
    CORS(app)

    from .auth import auth_bp
    from .routes import api

    app.register_blueprint(api)
    app.register_blueprint(auth_bp)
    return app


app = create_app()
