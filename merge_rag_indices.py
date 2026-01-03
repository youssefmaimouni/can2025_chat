"""
Merge Wiki RAG and CAN 2025 data into a single unified RAG index.
"""

import json
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# Load embedding model
model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

def clean(value):
    return "Unknown" if str(value).lower() == "nan" else value

def load_wiki_documents():
    """Load existing Wiki documents."""
    try:
        with open("wiki_documents.json", "r", encoding="utf-8") as f:
            docs = json.load(f)
        print(f"✅ Loaded {len(docs)} Wiki documents")
        return docs
    except FileNotFoundError:
        print("⚠️  Wiki documents not found")
        return []

def load_can2025_data():
    """Load CAN 2025 structured data."""
    try:
        with open("can2025_structured.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("⚠️  CAN 2025 data not found")
        return {}
def extract_squads_documents(can_data):
    """
    Extract squads (players + coaches) from CAN 2025 structured data
    and return formatted RAG documents.
    """
    documents = []

    squads = can_data.get("squads", {})
    if not isinstance(squads, dict):
        return documents

    for group_name, group_data in squads.items():
        if not isinstance(group_data, dict):
            continue

        for team_name, team_data in group_data.items():
            if not isinstance(team_data, dict):
                continue

            # -------- PLAYERS --------
            players = []
            for player in team_data.get("players", []):
                if isinstance(player, dict):
                    name = player.get("name", "Unknown")
                    position = player.get("position", "Unknown")
                    club = player.get("club", "Unknown")
                    players.append(f"{name} ({position}, {club})")

            if players:
                documents.append(
                    f"{team_name} squad players in {group_name}: "
                    + "; ".join(players)
                )

            # -------- COACH --------
            coach = team_data.get("coach")
            if coach:
                documents.append(
                    f"Coach of {team_name} in {group_name}: {coach}"
                )

    print(f"✅ Extracted {len(documents)} squad-related documents")
    return documents

def extract_referees_documents(can_data):
    """
    Extract referees information from CAN 2025 structured data
    and return formatted RAG documents.
    """
    documents = []

    referees = can_data.get("referees", [])
    if not isinstance(referees, list):
        return documents

    for ref in referees:
        if not isinstance(ref, dict):
            continue

        country = ref.get("country", "Unknown country")
        referee = ref.get("referee", "Unknown referee")
        assistants = ref.get("assistant_referees", [])
        matches = ref.get("matches_assigned", "Unknown matches")

        assistants_text = ""
        if isinstance(assistants, list) and assistants:
            assistants_text = " Assistants: " + ", ".join(assistants)

        doc = (
            f"Referee {referee} from {country} officiates matches: "
            f"{matches}.{assistants_text}"
        )

        documents.append(doc)

    print(f"✅ Extracted {len(documents)} referee-related documents")
    return documents

def extract_qualified_teams_documents(can_data):
    """
    Extract qualified teams information for AFCON 2025
    and return formatted RAG documents.
    """
    documents = []

    qualified_teams = can_data.get("qualified_teams", [])
    if not isinstance(qualified_teams, list):
        return documents

    for team in qualified_teams:
        if not isinstance(team, dict):
            continue

        name = team.get("Team", "Unknown team")
        qualified_as = team.get("Qualified as", "Unknown qualification")
        qualified_on = team.get("Qualified on", "Unknown date")
        appearances = team.get(
            "Previous appearances in Africa Cup of Nations1",
            "Unknown appearances"
        )

        doc = (
            f"{name} qualified for AFCON 2025 as {qualified_as} "
            f"on {qualified_on}. "
            f"Previous AFCON appearances: {appearances}"
        )

        documents.append(doc)

    print(f"✅ Extracted {len(documents)} qualified-teams documents")
    return documents


def format_can_documents(can_data):
    """Convert CAN 2025 data into document format for RAG."""
    documents = []

    # 1. Groups and Teams
    if "groups" in can_data:
        for group_name, teams in can_data["groups"].items():
            group_name_clean = group_name.upper().strip()
            doc = f"AFCON 2025 FINAL TOURNAMENT {group_name_clean} teams: {', '.join(teams)}"
            documents.append(doc)

    # 2. Squads (players + coaches)
    if "squads" in can_data:
        squad_docs = extract_squads_documents(can_data)
        documents.extend(squad_docs)


    # 3. Venues
    if "venues" in can_data:
        for venue in can_data["venues"]:
            doc = f"Stadium: {venue.get('stadium', 'Unknown')} in {venue.get('city', 'Unknown')}. Capacity: {venue.get('capacity', 'Unknown')}"
            documents.append(doc)

    # 4. Man of the Match
    if "man_of_the_match" in can_data:
        motm_list = []
        for match in can_data["man_of_the_match"]:
            stage = match.get("Stage_Group stage matches", "")
            if stage and "Knock-out" not in stage and stage not in ["Knock-out stage matches"]:
                team1 = match.get("Team 1_Group stage matches", "")
                team2 = match.get("Team 2_Group stage matches", "")
                result = match.get("Result_Group stage matches", "")
                motm = match.get("Man of the Match_Group stage matches", "")
                
                if team1 and team2 and isinstance(motm, str) and motm not in ["NaN", ""]:
                    motm_list.append(f"{team1} vs {team2} ({result}): {motm}")
        
        if motm_list:
            doc = f"Players of the Match: {'; '.join(motm_list[:20])}"
            documents.append(doc)

    # 5. Discipline Records
    if "discipline" in can_data:
        discipline_list = []
        for record in can_data["discipline"]:
            player = record.get("Player(s)/Official(s)_Group stage suspensions", "")
            if player and player != "Knock-out stage suspensions":
                offence = record.get("Offence(s)_Group stage suspensions", "")
                suspension = record.get("Suspension(s)_Group stage suspensions", "")
                discipline_list.append(f"{player}: {offence} → {suspension}")
        
        if discipline_list:
            doc = f"Tournament Discipline Records: {'; '.join(discipline_list[:15])}"
            documents.append(doc)
    
    # 6. Referees
    if "referees" in can_data:
        referee_docs = extract_referees_documents(can_data)
        documents.extend(referee_docs)

    # 7. Qualified Teams
    if "qualified_teams" in can_data:
        qualified_docs = extract_qualified_teams_documents(can_data)
        documents.extend(qualified_docs)


    print(f"✅ Formatted {len(documents)} CAN 2025 documents")
    return documents

def merge_and_index():
    """Merge Wiki and CAN 2025 data and create unified index."""
    
    print("=" * 60)
    print("Merging Wiki and CAN 2025 RAG Indices")
    print("=" * 60)
    
    # Load data
    print("\n📂 Loading data sources...")
    wiki_docs = load_wiki_documents()
    can_data = load_can2025_data()
    can_docs = format_can_documents(can_data)
    
    # Merge documents
    print(f"\n🔗 Merging documents...")
    all_documents = wiki_docs + can_docs
    print(f"   • Wiki docs: {len(wiki_docs)}")
    print(f"   • CAN 2025 docs: {len(can_docs)}")
    print(f"   • Total: {len(all_documents)}")
    
    # Create embeddings
    print(f"\n🔢 Creating embeddings for {len(all_documents)} documents...")
    embeddings = model.encode(all_documents, convert_to_numpy=True)
    
    # Create FAISS index
    print("📊 Building FAISS index...")
    index = faiss.IndexFlatL2(embeddings.shape[1])
    index.add(embeddings.astype(np.float32))
    
    # Save index and documents
    print("\n💾 Saving files...")
    faiss.write_index(index, "rag_faiss.index")
    
    # Save documents as JSON (with simple format for easy reference)
    with open("rag_documents.json", "w", encoding="utf-8") as f:
        json.dump(all_documents, f, indent=2, ensure_ascii=False)
    
    print("=" * 60)
    print("✅ Unified RAG Index Created!")
    print("=" * 60)
    print("\n📊 Summary:")
    print(f"   Index: rag_faiss.index")
    print(f"   Documents: rag_documents.json")
    print(f"   Total documents: {len(all_documents)}")
    print(f"   Embedding dimension: {embeddings.shape[1]}")
    print("\n✨ Ready to use in app.py!")

if __name__ == "__main__":
    merge_and_index()
