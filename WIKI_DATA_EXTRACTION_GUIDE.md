# CAF Chatbot - Wikipedia Data Extraction Guide

## Your Current Setup
You have a **RAG (Retrieval-Augmented Generation) chatbot** that uses:
- **FAISS Index** for semantic search
- **RAG Documents JSON** (match data formatted as natural sentences)
- **SQLite Database** for structured match queries
- **LLM** (Mistral 7B) for conversational responses

## Strategy for Wiki API Data Extraction

### 1. **Extract Multiple Data Sources**
```python
WIKI_PAGES = [
    "African_Footballer_of_the_Year",
    "African_Nations_Championship",
    "CAF_Champions_League",
    "CAF_Confederation_Cup",
    "African_football_records",
    "List_of_African_national_football_teams"
]
```

### 2. **Data Extraction Process**

#### Option A: Extract as Text Documents (for RAG)
Convert Wikipedia sections → Natural language sentences → FAISS embeddings
```
Section: "Winners"
Raw: "Egypt has won 7 times..."
→ Convert to: "Egypt won the African Footballer of the Year award 7 times."
→ Add to rag_documents.json
→ Embed with SentenceTransformer
```

#### Option B: Extract Structured Data (for SQL)
Extract tables/statistics → JSON/CSV → SQLite database
```
Table with columns: award_year, player_name, country, club, position
→ Store in matches.db
→ Query via SQL when user asks specific questions
```

### 3. **Implementation Steps**

**Step 1:** Extract & Clean Wikipedia Data
```python
import wikipediaapi
import json
import re

def extract_wiki_data(page_title):
    wiki = wikipediaapi.Wikipedia(
        user_agent='CAFChatbot/1.0',
        language='en',
        extract_format=wikipediaapi.ExtractFormat.WIKI
    )
    
    page = wiki.page(page_title)
    
    data = {
        "title": page.title,
        "summary": page.summary[:500],  # First 500 chars
        "sections": []
    }
    
    # Extract all sections
    for section in page.sections:
        section_data = {
            "title": section.title,
            "text": section.text[:1000]  # Limit text length
        }
        data["sections"].append(section_data)
    
    return data
```

**Step 2:** Convert to Natural Language (for RAG)
```python
def convert_to_rag_documents(wiki_data):
    documents = []
    
    for section in wiki_data["sections"]:
        title = section["title"]
        text = section["text"]
        
        # Clean and split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        for sentence in sentences:
            if len(sentence.strip()) > 10:
                # Add context
                doc = f"{wiki_data['title']} - {title}: {sentence.strip()}"
                documents.append(doc)
    
    return documents
```

**Step 3:** Create FAISS Index
```python
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np

def build_faiss_index(documents):
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(documents, convert_to_numpy=True)
    
    # Create FAISS index
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    
    # Save
    faiss.write_index(index, "wiki_faiss.index")
    
    with open("wiki_documents.json", "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False)
    
    return index
```

## Full Example Script

Create `extract_wiki_caf.py`:

```python
import wikipediaapi
import json
import re
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# 1. EXTRACT DATA
WIKI_PAGES = {
    "African_Footballer_of_the_Year": "Awards",
    "African_Nations_Championship": "Tournaments",
    "CAF_Champions_League": "Club Competitions"
}

def extract_all_wiki_data():
    wiki = wikipediaapi.Wikipedia(
        user_agent='CAFChatbot/1.0 (contact@example.com)',
        language='en',
        extract_format=wikipediaapi.ExtractFormat.WIKI
    )
    
    all_documents = []
    
    for page_title, category in WIKI_PAGES.items():
        print(f"Extracting: {page_title}...")
        page = wiki.page(page_title)
        
        if not page.exists():
            print(f"  ❌ Page not found: {page_title}")
            continue
        
        # Add summary
        if page.summary:
            all_documents.append(
                f"[{category}] {page_title}: {page.summary[:300]}"
            )
        
        # Add all sections
        for section in page.sections:
            text = section.text
            sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
            
            for sentence in sentences[:5]:  # Limit per section
                doc = f"[{category}] {page_title} - {section.title}: {sentence}"
                all_documents.append(doc)
    
    return all_documents

# 2. BUILD INDEX
def build_index(documents):
    print(f"Building FAISS index for {len(documents)} documents...")
    
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(documents, convert_to_numpy=True)
    
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    
    faiss.write_index(index, "wiki_faiss.index")
    
    with open("wiki_documents.json", "w", encoding="utf-8") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Index created with {len(documents)} documents")
    return index

# 3. TEST SEARCH
def test_search(query):
    model = SentenceTransformer("all-MiniLM-L6-v2")
    index = faiss.read_index("wiki_faiss.index")
    
    with open("wiki_documents.json", "r", encoding="utf-8") as f:
        documents = json.load(f)
    
    emb = model.encode([query], convert_to_numpy=True)
    _, idx = index.search(emb, k=3)
    
    print(f"\n🔍 Query: '{query}'")
    for i, doc_idx in enumerate(idx[0], 1):
        print(f"{i}. {documents[doc_idx][:100]}...")

# MAIN
if __name__ == "__main__":
    docs = extract_all_wiki_data()
    index = build_index(docs)
    
    # Test searches
    test_search("Who won African Footballer of the Year?")
    test_search("CAF Champions League winners")
```

## Integration with Your App

Update your `app.py` to use Wiki data:

```python
# Option 1: Use Wiki-specific index
with open("wiki_documents.json", "r", encoding="utf-8") as f:
    wiki_documents = json.load(f)
wiki_index = faiss.read_index("wiki_faiss.index")

# Option 2: Combine both indices
def hybrid_search(query, k=5):
    # Search match database
    db_results = rag_search(query, k=3)
    
    # Search Wikipedia
    emb = model.encode([query], convert_to_numpy=True)
    _, idx = wiki_index.search(emb, k=2)
    wiki_results = [wiki_documents[i] for i in idx[0]]
    
    return db_results + wiki_results
```

## Advantages of This Approach

✅ **Flexible** - RAG handles unstructured text from Wikipedia  
✅ **Scalable** - Can add more pages/sources easily  
✅ **Semantic** - FAISS finds relevant info by meaning, not keywords  
✅ **Fast** - Vector search is much faster than full-text search  
✅ **Hybrid** - Combine structured (SQL) + unstructured (RAG) data  

## Quick Start

```bash
# Install if needed
pip install wikipediaapi faiss-cpu sentence-transformers

# Run extraction
python extract_wiki_caf.py

# Test it
python app.py
```
