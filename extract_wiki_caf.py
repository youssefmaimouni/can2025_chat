import wikipediaapi
import json
import re
import requests
from bs4 import BeautifulSoup
from io import StringIO
import pandas as pd
import os
import sys
import traceback

# Optional heavy deps (faiss / sentence-transformers) used only if available
try:
    import faiss
    import numpy as np
    from sentence_transformers import SentenceTransformer
    HAS_FAISS = True
except Exception:
    HAS_FAISS = False

QUALIFIED_COUNTRIES = [
    "Morocco", "Algeria", "Egypt", "Senegal", "Ivory Coast", "Côte d'Ivoire",
    "Nigeria", "Tunisia", "Cameroon", "Mali", "South Africa", "DR Congo",
    "Burkina Faso", "Equatorial Guinea", "Gabon", "Zambia", "Uganda",
    "Angola", "Benin", "Botswana", "Sudan", "Comoros", "Zimbabwe",
    "Tanzanie", "Tanzania", "Mozambique"
]

WIKI_PAGES = {
    "2025_Africa_Cup_of_Nations": "Current Tournament",
    "2025_Africa_Cup_of_Nations_squads": "Full Squads and Players",
    "2025_Africa_Cup_of_Nations_qualification": "Qualification Journey",
    "African_Cup_of_Nations": "Tournament History",
    "Morocco_national_football_team": "Host Team Info",
}

# User-selected sections to keep (edit this mapping in-code)
MY_PICKY_DATA = {
    "2025_Africa_Cup_of_Nations": [
        "Host selection", "Prize money", "Qualification", "Qualified teams",
        "Venues", "Squads", "Match officials", "Draw", "Group stage",
        "Group A", "Group B", "Group C", "Group D", "Group E", "Group F",
        "Ranking of third-placed teams", "Knockout stage", "Round of 16",
        "Quarter-finals", "Semi-finals", "Third place play-off", "Final",
        "Statistics", "Goalscorers", "Discipline", "Man of the match",
    ],
    "2025_Africa_Cup_of_Nations_squads": [
        "Group A", "Comoros", "Mali", "Morocco", "Zambia",
        "Group B", "Angola", "Egypt", "South Africa", "Zimbabwe",
        "Group C", "Nigeria", "Tanzania", "Tunisia", "Uganda",
        "Group D", "Benin", "Botswana", "DR Congo", "Senegal",
        "Group E", "Algeria", "Burkina Faso", "Equatorial Guinea", "Sudan",
        "Group F", "Cameroon", "Gabon", "Ivory Coast", "Mozambique",
    ],
    "2025_Africa_Cup_of_Nations_qualification": [
        "Entrants", "Preliminary round", "Group stage",
        "Group A", "Group B", "Group C", "Group D", "Group E", "Group F",
        "Group G", "Group H", "Group I", "Group J", "Group K", "Group L",
        "Goalscorers", "Qualified teams",
    ],
    "African_Cup_of_Nations": [
        "History", "Format", "Qualifying", "Final phase", "Records and statistics", "Awards",
    ],
    "Morocco_national_football_team": [
        "History", "Results and fixtures", "2025", "Coaching staff", "Players",
        "Current squad", "Player records", "Top goalscorers", "Competitive record",
        "Africa Cup of Nations", "Honours", "Summary",
    ],
}

SELECTED_FILE = "selected_sections.json"


def clean_text(text):
    if not text:
        return ""
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\(.*?\)", "", text)
    return text.strip()


def extract_squad_data_full(page_title, category, filter_teams=None):
    url = f"https://en.wikipedia.org/wiki/{page_title}"
    documents = []
    headers = {'User-Agent': 'CAFChatbot/1.0 (contact@example.com)'}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, 'html.parser')
        current_country = "Unknown Team"
        current_coach = "Unknown Coach"
        for element in soup.find_all(['h2', 'h3', 'h4', 'p', 'table']):
            if element.name in ['h2', 'h3', 'h4']:
                headline = element.find('span', class_='mw-headline')
                raw_title = headline.get_text().strip() if headline else element.get_text().strip()
                clean_title = clean_text(raw_title)
                is_valid = any(country.lower() in clean_title.lower() for country in QUALIFIED_COUNTRIES)
                if is_valid:
                    current_country = clean_title
                    current_coach = "Unknown Coach"
            elif element.name == 'p' and "Head coach" in element.get_text():
                full_text = element.get_text().strip()
                coach_match = re.search(r"Head coach:\s*([^\[\n]+)", full_text)
                if coach_match:
                    current_coach = clean_text(coach_match.group(1))
                    coach_doc = f"[{category}] {current_country} Manager: {current_coach}"
                    if filter_teams is None or any(t.lower() in current_country.lower() for t in filter_teams):
                        documents.append(coach_doc)
            elif element.name == 'table':
                if current_country != "Unknown Team" and "Contents" not in current_country:
                    try:
                        df = pd.read_html(StringIO(str(element)))[0]
                        cols = [str(c) for c in df.columns]
                        if any(x in cols for x in ['Player', 'Pos.', 'Club']):
                            for _, row in df.iterrows():
                                raw_name = str(row.get('Player', 'Unknown'))
                                clean_name = clean_text(raw_name)
                                if not clean_name or clean_name == 'Unknown':
                                    continue
                                pos = str(row.get('Pos.', 'Player'))
                                club = clean_text(str(row.get('Club', 'Unknown club')))
                                doc = (f"[{category}] {current_country} Player: {clean_name} is a {pos} "
                                       f"playing for {club}. Head coach: {current_coach}.")
                                if filter_teams is None or any(t.lower() in current_country.lower() for t in filter_teams):
                                    documents.append(doc)
                    except Exception:
                        continue
    except Exception as e:
        print(f"⚠️ Error in extract_squad_data_full for {page_title}: {e}")
    return documents


def extract_wiki_page(page_title, category):
    wiki = wikipediaapi.Wikipedia(user_agent='CAFChatbot/1.0', language='en', extract_format=wikipediaapi.ExtractFormat.WIKI)
    page = wiki.page(page_title)
    if not page.exists():
        return []
    docs = [f"[{category}] {page_title} Summary: {page.summary[:1000]}"]

    def get_sections(sections):
        res = []
        for s in sections:
            if s.title.lower() not in ["references", "external links", "see also", "notes", "contents"]:
                if len(s.text) > 40:
                    res.append(f"[{category}] {page_title} - {s.title}: {s.text[:2000]}")
                res.extend(get_sections(s.sections))
        return res

    docs.extend(get_sections(page.sections))
    return docs


def find_section_by_title(sections, desired):
    for s in sections:
        if s.title.strip().lower() == desired.strip().lower():
            return s
        found = find_section_by_title(s.sections, desired)
        if found:
            return found
    return None


def extract_section_text(page_title, section_title):
    wiki = wikipediaapi.Wikipedia(user_agent='CAFChatbot/1.0', language='en')
    page = wiki.page(page_title)
    if not page.exists():
        return None
    if section_title.lower() in ["summary", "intro", "introduction"]:
        return page.summary
    s = find_section_by_title(page.sections, section_title)
    if s:
        return s.text
    return None


def run_config(selected_map=None):
    wiki = wikipediaapi.Wikipedia(user_agent='CAFChatbot/1.0', language='en')
    if not selected_map:
        selected_map = MY_PICKY_DATA
    all_documents = []
    for page_title, sections in selected_map.items():
        cat = WIKI_PAGES.get(page_title, page_title)
        try:
            # General page text and sections
            page_docs = extract_wiki_page(page_title, cat)
            all_documents.extend(page_docs)
            # Specific selected sections (full content)
            for sec in sections:
                txt = extract_section_text(page_title, sec)
                if txt and len(txt.strip()) > 20:
                    all_documents.append(f"[{cat}] {page_title} - {sec}: {clean_text(txt)}")
            # Squads structured extraction when applicable
            if 'squad' in page_title.lower():
                docs = extract_squad_data_full(page_title, cat, filter_teams=sections)
                all_documents.extend(docs)
        except Exception:
            print(f"Error extracting {page_title}:\n", traceback.format_exc())

    # Save outputs
    with open('manual_wiki_docs.json', 'w', encoding='utf-8') as f:
        json.dump(all_documents, f, ensure_ascii=False, indent=2)
    with open('wiki_documents.json', 'w', encoding='utf-8') as f:
        json.dump(all_documents, f, ensure_ascii=False, indent=2)
    print(f"Extraction complete — {len(all_documents)} fragments saved to manual_wiki_docs.json and wiki_documents.json.")

    # Optional FAISS indexing
    if HAS_FAISS and all_documents:
        try:
            print('Building FAISS index (optional)...')
            model = SentenceTransformer('all-MiniLM-L6-v2')
            embeddings = model.encode(all_documents, show_progress_bar=True)
            index = faiss.IndexFlatL2(embeddings.shape[1])
            index.add(np.array(embeddings).astype('float32'))
            faiss.write_index(index, 'wiki_faiss.index')
            print('FAISS index saved as wiki_faiss.index')
        except Exception:
            print('FAISS indexing failed:', traceback.format_exc())


def main():
    # Run non-interactively by default using MY_PICKY_DATA
    print('\nRunning extraction using in-code `MY_PICKY_DATA` configuration...')
    run_config(MY_PICKY_DATA)


if __name__ == '__main__':
    main()
