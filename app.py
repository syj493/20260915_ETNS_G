import os
import sqlite3
from functools import wraps
from pathlib import Path

from flask import Flask, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path("/tmp/todos.db") if os.environ.get("VERCEL") else BASE_DIR / "todos.db"
DATABASE_URL = os.environ.get("SUPABASE_DB_URL") or os.environ.get("POSTGRES_URL")

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD_HASH = os.environ.get("ADMIN_PASSWORD_HASH", "")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-secret-key-change-me")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == ADMIN_USERNAME and ADMIN_PASSWORD_HASH and check_password_hash(
            ADMIN_PASSWORD_HASH, password
        ):
            session["logged_in"] = True
            session["username"] = username
            return redirect(url_for("index"))
        error = "아이디 또는 비밀번호가 올바르지 않습니다."
    return render_template("login.html", error=error)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))

if DATABASE_URL:
    import psycopg2
    import psycopg2.extras


def get_db():
    if "db" not in g:
        if DATABASE_URL:
            g.db = psycopg2.connect(
                DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor
            )
        else:
            g.db = sqlite3.connect(DB_PATH)
            g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL)
        conn.cursor().execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                done BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS todos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
    conn.commit()
    conn.close()


init_db()


@app.route("/")
@login_required
def index():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM todos ORDER BY done ASC, id DESC")
    todos = cur.fetchall()
    remaining = sum(1 for t in todos if not t["done"])
    return render_template(
        "index.html", todos=todos, remaining=remaining, username=session.get("username")
    )


@app.route("/add", methods=["POST"])
@login_required
def add():
    title = request.form.get("title", "").strip()
    if title:
        db = get_db()
        cur = db.cursor()
        cur.execute(
            "INSERT INTO todos (title) VALUES (%s)" if DATABASE_URL
            else "INSERT INTO todos (title) VALUES (?)",
            (title,),
        )
        db.commit()
    return redirect(url_for("index"))


@app.route("/toggle/<int:todo_id>", methods=["POST"])
@login_required
def toggle(todo_id):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "UPDATE todos SET done = NOT done WHERE id = %s" if DATABASE_URL
        else "UPDATE todos SET done = 1 - done WHERE id = ?",
        (todo_id,),
    )
    db.commit()
    return redirect(url_for("index"))


@app.route("/delete/<int:todo_id>", methods=["POST"])
@login_required
def delete(todo_id):
    db = get_db()
    cur = db.cursor()
    cur.execute(
        "DELETE FROM todos WHERE id = %s" if DATABASE_URL
        else "DELETE FROM todos WHERE id = ?",
        (todo_id,),
    )
    db.commit()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)
