# AFCON 2025 AI Assistant – Backend, Data & Chatbot Logic

## 📌 Overview
This part of the project contains the **core logic** of the AFCON 2025 AI Assistant.  
It includes:
- The Flask backend API
- Data collection and preprocessing pipelines
- The AI chatbot logic (Agent + RAG + SQL)

This backend is responsible for providing reliable, explainable, and data-grounded answers to user questions.

---

## 🏗️ Global Architecture
The backend follows a **modular and layered architecture**:

- API Layer (Flask)
- Agent Decision Layer (SQL / RAG / BOTH)
- Intelligence Layer (RAG + LLM)
- Data Layer (SQLite + FAISS + JSON)

This design ensures scalability, maintainability, and reduced hallucinations.

---

## 🧠 Backend – Flask API

### Responsibilities
- Expose REST endpoints for the frontend
- Orchestrate AI reasoning tools
- Execute secure SQL queries
- Retrieve contextual information via RAG
- Communicate with the LLM (OpenRouter)

### Main Technologies
- Python
- Flask
- SQLite
- FAISS
- Sentence Transformers
- OpenRouter API (Mistral LLM)

### Main Files
```

backend/
│── app.py                  # Main Flask application
│── matches.db              # SQLite database
│── rag_faiss.index         # FAISS vector index
│── rag_documents.json      # RAG documents
│── .env                    # Environment variables

````

### Environment Variables
Create a `.env` file:
```env
OPENROUTER_API_KEY=your_api_key_here
````

### Run Backend

```bash
python app.py
```

Server runs on:

```
http://localhost:5000
```

### API Endpoints

* `POST /api/ask` → Chatbot interaction
* `GET /health` → Backend health check

---

## 📊 Data Collection & Processing

### Purpose

This module is responsible for **collecting, cleaning, and preparing data** used by the AI system.

### Data Sources

* Wikipedia (AFCON 2025)
* Structured CAN 2025 data (JSON)
* Historical AFCON match dataset (CSV)

### Processing Pipeline

1. Extract raw data
2. Clean and normalize fields
3. Convert data into structured formats
4. Store match data into SQLite
5. Convert textual data into RAG documents
6. Build FAISS vector index

### Technologies Used

* Python
* Pandas
* SQLite
* JSON

### Files

```
data/
│── can2025_structured.json
│── wiki_documents.json
│── Caf_finals_and_qualifier.csv
│── create_db.py
│── merge_rag_indices.py
```

### Create SQLite Database

```bash
python create_db.py
```

### Build RAG Index

```bash
python merge_rag_indices.py
```

### Outputs

* `matches.db`
* `rag_faiss.index`
* `rag_documents.json`

---

## 🤖 Chatbot Logic & AI Agent

### Overview

The chatbot uses an **Agent-based architecture** to decide how each user question should be answered.

Instead of relying purely on a language model, the system combines:

* Deterministic data (SQL)
* Contextual knowledge (RAG)
* Natural language generation (LLM)

---

### Agent Decision Strategy

For each question, the agent selects one of the following tools:

* **SQL**
  Used for numerical or historical questions
  Example: *“How many goals did Egypt score in AFCON history?”*

* **RAG**
  Used for descriptive or contextual questions
  Example: *“Who is the coach of Morocco?”*

* **BOTH**
  Used when both statistics and context are required

The agent always returns a **strict JSON decision**.

---

### RAG (Retrieval-Augmented Generation)

* Embedding model: `all-MiniLM-L6-v2`
* Vector store: FAISS
* Documents: Wikipedia + CAN 2025 structured data

RAG ensures that answers are **grounded in verified information**.

---

### SQL Analytics

* Database: SQLite
* Table: `matches`
* Used for accurate statistical answers
* SQL queries are validated to prevent unsafe operations

---

### Anti-Hallucination Measures

* RAG-based grounding
* SQL-based factual answers
* Low-temperature generation
* Explicit prompt constraints
* No external knowledge beyond provided context

---

## 🔐 Security & Reliability

* SQL injection prevention
* Controlled prompt generation
* Error handling and logging
* Separation of responsibilities

---
## 🌐 Frontend Application

The frontend of the **AFCON 2025 AI Assistant** is developed as a separate React application.

🔗 **Frontend GitHub Repository**:  
https://github.com/youssefmaimouni/can-2025-fan-hub.git

### Frontend Responsibilities
- Display AFCON 2025 tournament statistics
- Provide an interactive chatbot user interface
- Handle user interactions and API requests
- Communicate with the backend via REST APIs

### Frontend Technologies
- React
- JavaScript (ES6+)
- HTML5 / CSS3
- Vite (development environment)

### How It Connects to the Backend
The frontend communicates with the backend through the following endpoint:

---

## 🚀 Future Improvements

* Real-time match data integration
* Multilingual chatbot (Arabic / French / English)
* Source citations in answers
* Cloud deployment (Docker, Render, AWS)
* Performance optimization for large-scale usage

---

## 👤 Author

**Youssef Maimouni**

## 📅 Year

2026