from flask import Flask, request, jsonify, render_template
import sqlite3
import os
from openai import OpenAI

app = Flask(__name__)

import os

client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1"
)
# 🗄️ INIT DATABASE
def init_db():
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()

    # Messages table
    c.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id TEXT,
        role TEXT,
        content TEXT
    )
    """)

    # Chats table (for titles)
    c.execute("""
    CREATE TABLE IF NOT EXISTS chats (
        chat_id TEXT PRIMARY KEY,
        title TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# 🏠 HOME
@app.route("/")
def home():
    return render_template("index.html")

# 💬 CHAT API
@app.route("/chat", methods=["POST"])
def chat():
    data = request.json

    user_message = data.get("message", "")
    chat_id = data.get("chat_id", "default")

    conn = sqlite3.connect("chat.db")
    c = conn.cursor()

    # 🧠 CREATE TITLE IF NEW CHAT
    c.execute("SELECT title FROM chats WHERE chat_id = ?", (chat_id,))
    row = c.fetchone()

    if row is None:
        try:
            title_prompt = f"Give a short 3-4 word title: {user_message}"

            response = client.chat.completions.create(
                model="openrouter/auto",
                messages=[{"role": "system", "content": "You are a helpful assistant."}]
            )
            title = response.choices[0].message.content.strip()

        except Exception as e:
            print("Title error:", e)
            title = "New Chat"

        c.execute(
            "INSERT INTO chats (chat_id, title) VALUES (?, ?)",
            (chat_id, title)
        )
        conn.commit()

    # 💾 SAVE USER MESSAGE
    c.execute(
        "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
        (chat_id, "user", user_message)
    )
    conn.commit()

    # 📜 LOAD CHAT HISTORY
    c.execute(
        "SELECT role, content FROM messages WHERE chat_id = ?",
        (chat_id,)
    )

    history = [{"role": row[0], "content": row[1]} for row in c.fetchall()]

    try:
        response = client.chat.completions.create(
            model="openai/gpt-3.5-turbo",
            messages=[{"role": "system", "content": "You are a helpful assistant."}] + history
        )

        bot_reply = response.choices[0].message.content

    except Exception as e:
        print("FULL ERROR:", str(e))
        bot_reply = "Error getting response"

    # 💾 SAVE BOT MESSAGE
    c.execute(
    "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
    (chat_id, "assistant", bot_reply)
)
    conn.commit()
    conn.close()

    return jsonify({"reply": bot_reply})

# 📂 GET ALL CHATS (Sidebar)
@app.route("/chats")
def get_chats():
    conn = sqlite3.connect("chat.db")
    c = conn.cursor()

    c.execute("SELECT chat_id, title FROM chats ORDER BY rowid DESC")
    chats = [{"id": row[0], "title": row[1]} for row in c.fetchall()]

    conn.close()
    return jsonify(chats)

# 📜 LOAD SINGLE CHAT
@app.route("/load_chat", methods=["POST"])
def load_chat():
    data = request.json
    chat_id = data.get("chat_id")

    conn = sqlite3.connect("chat.db")
    c = conn.cursor()

    c.execute(
        "SELECT role, content FROM messages WHERE chat_id = ?",
        (chat_id,)
    )

    messages = [{"role": row[0], "content": row[1]} for row in c.fetchall()]

    conn.close()
    return jsonify(messages)

# ▶️ RUN
import os

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)))
