import re

from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import execute_query, execute_write


auth_bp = Blueprint("auth", __name__)
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@auth_bp.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if len(name) < 2 or len(name) > 100:
        return jsonify({"status": "error", "message": "Nama harus 2-100 karakter"}), 400
    if not EMAIL_PATTERN.fullmatch(email):
        return jsonify({"status": "error", "message": "Email tidak valid"}), 400
    if len(password) < 8:
        return jsonify({"status": "error", "message": "Password minimal 8 karakter"}), 400

    existing = execute_query(
        "SELECT id FROM users WHERE email = %s LIMIT 1",
        (email,),
    )
    if existing:
        return jsonify({"status": "error", "message": "Email sudah terdaftar"}), 409

    user_id = execute_write(
        "INSERT INTO users (nama, email, password) VALUES (%s, %s, %s)",
        (name, email, generate_password_hash(password)),
    )

    return jsonify(
        {
            "status": "success",
            "message": "Registrasi berhasil",
            "user": {"id": user_id, "name": name, "email": email},
        }
    ), 201


@auth_bp.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = execute_query(
        "SELECT id, nama AS name, email, password FROM users WHERE email = %s LIMIT 1",
        (email,),
    )
    if not user or not check_password_hash(user[0]["password"], password):
        return jsonify({"status": "error", "message": "Email atau password salah"}), 401

    return jsonify(
        {
            "status": "success",
            "message": "Login berhasil",
            "user": {
                "id": user[0]["id"],
                "name": user[0]["name"],
                "email": user[0]["email"],
            },
        }
    ), 200
