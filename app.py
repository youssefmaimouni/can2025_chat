import os
import json
import sqlite3
import requests
import faiss
import numpy as np
import re
from flask import Flask, render_template, request
from flask import jsonify
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from flask_cors import CORS

# Load environment variables
load_dotenv()

# ======================
# CONFIGURATION
# ======================
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# Using a stable free model from OpenRouter
OPENROUTER_MODEL = "mistralai/mistral-7b-instruct:free"
DB_PATH = "matches.db"

app = Flask(__name__)
CORS(app)
# ======================
# LOAD RAG SYSTEM
# ======================
# Load Embedding Model
model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

# LOAD UNIFIED RAG INDEX (Wiki + CAN 2025 + Match History)
rag_index = None
rag_documents = []
try:
    rag_index = faiss.read_index("rag_faiss.index")
    with open("rag_documents.json", "r", encoding="utf-8") as f:
        rag_documents = json.load(f)
    print(f"✅ Unified RAG Index loaded ({len(rag_documents)} documents).")
except Exception as e:
    print(f"⚠️ RAG Index not found: {e}")
    print("   Run: python merge_rag_indices.py")

# ======================
# TOOLS & HELPERS
# ======================

def run_sql_query(query):
    """Executes SQLite queries for statistics."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()
        conn.close()
        return rows
    except Exception as e:
        return f"SQL Error: {str(e)}"

def rag_search(query, k=25):
    if rag_index is None:
        return ""

    emb = model.encode([query], convert_to_numpy=True)
    _, idx = rag_index.search(emb, k)

    context = []
    for i in idx[0]:
        if i < len(rag_documents):
            context.append(rag_documents[i])

    return "\n".join(context)


def call_llm(messages, temperature=0):
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "User-Agent": "AFCON-2025-AI-Assistant"
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 500   # 🔥 CRUCIAL
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60
        )

        # 🔎 LOG COMPLET
        print("🔵 OpenRouter status:", response.status_code)
        print("🔵 OpenRouter raw:", response.text)

        if response.status_code != 200:
            return ""

        data = response.json()

        if "choices" in data and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"]

        return ""

    except Exception as e:
        print("❌ LLM ERROR:", e)
        return ""

# ======================
# AGENT LOGIC
# ======================

AGENT_PROMPT = """
You are the Official AFCON 2025 AI Expert. 
Current Date: December 30, 2025. Tournament Location: Morocco.

Your task: Decide if the question needs SQL, RAG, or BOTH.

TOOLS:
1. SQL: Use for counts, totals, or match results (e.g., "How many goals did Egypt score in 2010?").
   - Table: matches
   - Columns: date, home_team, away_team, home_score, away_score, tournament, country.
   - For AFCON, use: tournament LIKE '%African Cup of Nations%'

2. RAG: Use for 2025 details, current squads, head coaches, player bios, or stadium info.
   - Example: "Who is the coach of Zambia?", "Who does Brahim Diaz play for?", "Tell me about the Rabat stadium".

Return ONLY JSON:
{
  "tool": "SQL" | "RAG" | "BOTH",
  "sql_query": "SQL string or null",
  "rag_query": "Search terms or null"
}
"""

def agent_decide(question):
    response = call_llm([
        {"role": "system", "content": AGENT_PROMPT},
        {"role": "user", "content": question}
    ])

    if not response:
        return {"tool": "RAG", "sql_query": None, "rag_query": question}

    try:
        # Extraction JSON STRICT
        start = response.find("{")
        end = response.rfind("}") + 1
        decision = json.loads(response[start:end])

        if decision["tool"] not in ["SQL", "RAG", "BOTH"]:
            raise ValueError("Invalid tool")

        return decision

    except Exception as e:
        print("⚠️ JSON parsing failed:", response)
        return {"tool": "RAG", "sql_query": None, "rag_query": question}


def generate_final_answer(question, sql_result, rag_context):

    if not rag_context:
        rag_context = "No additional context found."

    prompt = f"""
You are the Official AFCON 2025 Expert.

Answer clearly and concisely using the provided context only.

User Question:
{question}

Context:
{rag_context}

Answer:
"""

    return call_llm([
        {"role": "system", "content": "You are a football data expert specialized in AFCON 2025."},
        {"role": "user", "content": prompt}
    ], temperature=0)

# ======================
# FLASK ROUTES
# ======================

@app.route("/", methods=["GET", "POST"])
def index_page():
    answer = ""
    user_question = ""

    if request.method == "POST":
        user_question = request.form["question"]

        # 1. Let the Agent decide what tools to use
        decision = agent_decide(user_question)

        sql_data = None
        rag_data = None

        # 2. Execute SQL if needed
        if decision["tool"] in ["SQL", "BOTH"] and decision["sql_query"]:
            sql_data = run_sql_query(decision["sql_query"])

        # 3. Execute RAG if needed (Searches both match data and Wiki data)
        if decision["tool"] in ["RAG", "BOTH"] and decision["rag_query"]:
            rag_data = rag_search(decision["rag_query"])
            print(f"DEBUG RAG: {rag_data}")

        if isinstance(rag_data, list):
            rag_data = "\n".join(rag_data)
        # 4. Generate the final polished answer
        answer = generate_final_answer(user_question, sql_data, rag_data)

    return render_template("index.html", answer=answer, question=user_question)

@app.route("/api/ask", methods=["POST"])
def api_ask():
    data = request.get_json()

    if not data or "question" not in data:
        return jsonify({"error": "Missing question"}), 400

    user_question = data["question"]

    # 1. Agent decision
    decision = agent_decide(user_question)

    sql_data = None
    rag_data = None

    # 2. SQL
    if decision["tool"] in ["SQL", "BOTH"] and decision["sql_query"]:
        sql_data = run_sql_query(decision["sql_query"])

    # 3. RAG
    if decision["tool"] in ["RAG", "BOTH"] and decision["rag_query"]:
        rag_data = rag_search(decision["rag_query"])

    if isinstance(rag_data, list):
        rag_data = "\n".join(rag_data)

    # 4. Final answer
    answer = generate_final_answer(user_question, sql_data, rag_data)

    return jsonify({
        "question": user_question,
        "answer": answer,
        "tool_used": decision["tool"],
        "sql_query": decision["sql_query"],
        "rag_used": bool(rag_data)
    })

# ======================
# START APP
# ======================
if __name__ == "__main__":
    app.run(debug=True, port=5000)