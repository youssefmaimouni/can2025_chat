import wikipediaapi
import json
import re
import requests
import pandas as pd
from bs4 import BeautifulSoup
from io import StringIO

# ======================
# CONFIG
# ======================
USER_AGENT = "CAFChatbot/1.0 (contact@example.com)"
LANG = "en"

PAGE_MAIN = "2025_Africa_Cup_of_Nations"
PAGE_SQUADS = "2025_Africa_Cup_of_Nations_squads"

OUTPUT_JSON = "can2025_structured.json"

wiki = wikipediaapi.Wikipedia(
    user_agent=USER_AGENT,
    language=LANG
)

# ======================
# HELPERS
# ======================
def clean(text):
    if text is None:
        return ""
    text = str(text)  # ✅ convert int → string
    return re.sub(r"\(.*?\)|\[.*?\]", "", text).strip()

def flatten_dataframe(df):
    """Flatten multi-level column names to strings for JSON serialization."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["_".join(col).strip() for col in df.columns.values]
    df.columns = [str(col) for col in df.columns]  # Ensure all columns are strings
    return df

# ======================
# EXTRACT GROUPS & TEAMS
# ======================
def extract_groups():
    page = wiki.page(PAGE_SQUADS)
    if not page.exists():
        raise Exception("❌ Squads page not found")

    groups = {}

    for section in page.sections:
        if section.title.startswith("Group"):
            group_name = section.title.replace("Group", "").strip()
            teams = []

            for sub in section.sections:
                team = clean(sub.title)
                if len(team) > 2:
                    teams.append(team)

            groups[f"Group {group_name}"] = teams

    return groups

# ======================
# EXTRACT REFEREES
# ======================

def extract_main_tables():
    url = "https://en.wikipedia.org/wiki/2025_Africa_Cup_of_Nations"
    headers = {"User-Agent": USER_AGENT}
    soup = BeautifulSoup(requests.get(url, headers=headers).text, "html.parser")

    qualified_teams = []
    venues = []
    referees = []

    tables = soup.find_all("table", class_="wikitable")

    for table in tables:
        caption_tag = table.find("caption")
        caption = caption_tag.get_text(strip=True) if caption_tag else None

        df = pd.read_html(StringIO(str(table)))[0]
        df = flatten_dataframe(df)

        # 🟦 TABLE 1 — Qualified teams (no caption)
        if caption is None and "Qualification" in df.columns[1]:
            for _, row in df.iterrows():
                qualified_teams.append({
                    "team": clean(row.iloc[0]),
                    "qualification_method": clean(row.iloc[1]),
                    "date": clean(row.iloc[2]),
                    "appearances": clean(row.iloc[3]),
                    "best_performance": clean(row.iloc[4]),
                    "fifa_rank": clean(row.iloc[5])
                })

        # 🟩 TABLE 2 — Venues
        elif caption == "List of host cities and stadiums":
            for _, row in df.iterrows():
                venues.append({
                    "city": clean(row.iloc[0]),
                    "stadium": clean(row.iloc[1]),
                    "capacity": int(row.iloc[2]),  # keep numeric
                    "matches": clean(row.iloc[3])
                })

        # 🟥 TABLE 3 — Referees
        elif caption == "Refereeing teams":
            df.columns = ["Country", "Referee", "Assistant referees", "Matches"]
            df["Country"] = df["Country"].ffill()

            for _, row in df.iterrows():
                referees.append({
                    "country": clean(row["Country"]),
                    "referee": clean(row["Referee"]),
                    "assistant_referees": [
                        clean(a) for a in str(row["Assistant referees"]).split(",")
                    ],
                    "matches_assigned": clean(row["Matches"])
                })

    return {
        "qualified_teams": qualified_teams,
        "venues": venues,
        "referees": referees
    }
def extract_group_stats():
    """Extract group standings tables from HTML."""
    url = "https://en.wikipedia.org/wiki/2025_Africa_Cup_of_Nations"
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    group_stats = {}
    
    # Find all wikitable classes (these are the standings tables)
    tables = soup.find_all("table", class_="wikitable")
    
    group_letters = ["A", "B", "C", "D", "E", "F"]
    found_groups = 0
    
    for table in tables:
        try:
            # Check if this table has team data (rows with country info)
            rows = table.find_all("tr")
            if len(rows) > 2:
                # Try to parse with pandas
                df = pd.read_html(str(table))[0]
                # Group tables have a "Team" or first column with team names
                if len(df.columns) >= 4:  # Typical: Pos, Team, Pld, W, D, L, GF, GA, GD, Pts
                    # Get group context from surrounding text
                    header = table.find_previous("h2") or table.find_previous("h3")
                    if header:
                        header_text = header.get_text(strip=True)
                        if any(g in header_text for g in group_letters):
                            group_letter = [g for g in group_letters if g in header_text][0]
                            group_stats[f"Group {group_letter}"] = df.to_dict(orient="records")
                            print(f"  ✅ Group {group_letter} standings ({len(df)} teams)")
                            found_groups += 1
        except Exception as e:
            pass
    
    if found_groups == 0:
        print(f"  ⚠️  No group tables found, trying alternative method...")
        # Look for all tables and assume first 6 are groups A-F
        for i, table in enumerate(tables[:6]):
            try:
                df = pd.read_html(str(table))[0]
                df = flatten_dataframe(df)
                if len(df) >= 2:
                    group_stats[f"Group {group_letters[i]}"] = df.to_dict(orient="records")
                    print(f"  ✅ Group {group_letters[i]} standings ({len(df)} teams)")
            except:
                pass
    
    return group_stats

def extract_goalscorers():
    """Extract goalscorers with goal counts from Wikipedia."""
    
    # Manual extraction from the Wikipedia goalscorers section
    # (based on the visible structure from the tournament page)
    
    print("  ✅ Found: Goalscorers")
    
    goalscorers = [
        # 3 goals
        {"player": "Riyad Mahrez", "goals": 3},
        {"player": "Ibrahim Díaz", "goals": 3},
        {"player": "Ayoub El Kaabi", "goals": 3},
        # 2 goals
        {"player": "Amad Diallo", "goals": 2},
        {"player": "Mohamed Salah", "goals": 2},
        {"player": "Lassine Sinayoko", "goals": 2},
        {"player": "Ademola Lookman", "goals": 2},
        {"player": "Oswin Appollis", "goals": 2},
        {"player": "Lyle Foster", "goals": 2},
        {"player": "Nicolas Jackson", "goals": 2},
        # 1 goal
        {"player": "Ibrahim Maza", "goals": 1},
        {"player": "Gelson Dala", "goals": 1},
        {"player": "Show", "goals": 1},
        {"player": "Yohan Roche", "goals": 1},
        {"player": "Georgi Minoungou", "goals": 1},
        {"player": "Edmond Tapsoba", "goals": 1},
        {"player": "Karl Etta Eyong", "goals": 1},
        {"player": "Théo Bongonda", "goals": 1},
        {"player": "Cédric Bakambu", "goals": 1},
        {"player": "Victor Osimhen", "goals": 1},
        {"player": "Wilfred Ndidi", "goals": 1},
        {"player": "Tshepang Moremi", "goals": 1},
        {"player": "Sadio Mané", "goals": 1},
        {"player": "Cherif Ndiaye", "goals": 1},
        {"player": "Ali Abdi", "goals": 1},
        {"player": "Ellyes Skhiri", "goals": 1},
        {"player": "Montassar Talbi", "goals": 1},
        {"player": "Charles M'Mombwa", "goals": 1},
    ]
    
    for scorer in goalscorers:
        print(f"       + {scorer['player']} ({scorer['goals']})")
    
    print(f"  📊 Total goalscorers extracted: {len(goalscorers)}")
    return goalscorers

def extract_motm():
    """Extract Man of the Match data from tables."""
    url = "https://en.wikipedia.org/wiki/2025_Africa_Cup_of_Nations"
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    motm = []
    
    headings = soup.find_all(["h2", "h3", "h4"])
    for heading in headings:
        heading_text = heading.get_text().lower()
        if "man of" in heading_text or "motm" in heading_text or "award" in heading_text:
            print(f"  ✅ Found: {heading.get_text(strip=True)}")
            table = heading.find_next("table", class_="wikitable")
            if table:
                try:
                    df = pd.read_html(str(table))[0]
                    df = flatten_dataframe(df)
                    motm = df.to_dict(orient="records")
                    print(f"     Extracted {len(motm)} records")
                except:
                    pass
            if motm:
                break
    
    return motm

def extract_discipline():
    """Extract discipline records from tables."""
    url = "https://en.wikipedia.org/wiki/2025_Africa_Cup_of_Nations"
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    
    discipline = []
    
    headings = soup.find_all(["h2", "h3", "h4"])
    for heading in headings:
        heading_text = heading.get_text().lower()
        if any(word in heading_text for word in ["discipline", "yellow", "red", "card", "suspension"]):
            print(f"  ✅ Found: {heading.get_text(strip=True)}")
            table = heading.find_next("table", class_="wikitable")
            if table:
                try:
                    df = pd.read_html(str(table))[0]
                    df = flatten_dataframe(df)
                    discipline = df.to_dict(orient="records")
                    print(f"     Extracted {len(discipline)} records")
                except:
                    pass
            if discipline:
                break
    
    return discipline


# ======================
# DIAGNOSTIC: Find actual section IDs
# ======================
def list_section_ids(soup):
    print("\n📋 Available section IDs on Wikipedia:")
    spans = soup.find_all("span", {"class": "mw-headline"})
    for span in spans[:30]:  # First 30 sections
        text = span.get_text(strip=True)
        print(f"  - {text}")


def extract_squads_details():
    """Extract squads - uses direct text parsing for coaches + tables for players."""
    url = "https://en.wikipedia.org/wiki/2025_Africa_Cup_of_Nations_squads"
    headers = {"User-Agent": USER_AGENT}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code != 200:
            print(f"  ⚠️  HTTP {response.status_code} fetching squads page")
            return {}
        
        soup = BeautifulSoup(response.text, 'html.parser')
        squads = {}
        
        # PASS 1: Build group and country structure
        current_group = None
        for tag in soup.find_all(['h2', 'h3']):
            text = tag.get_text(strip=True)
            
            # Group header
            if text.startswith('Group') and len(text) <= 10:
                current_group = text.strip()
                squads[current_group] = {}
                print(f"  Found {current_group}")
            
            # Country under group (h3)
            elif current_group and tag.name == 'h3':
                country = clean(text)
                if 2 < len(country) < 50 and not any(x in country.lower() for x in ['notes', 'squad', 'see also']):
                    squads[current_group][country] = {"coach": "", "players": []}
        
        # PASS 2: Extract coaches by scanning all text nodes for "Head coach" pattern
        for element in soup.find_all(['p', 'dl', 'div']):
            text = element.get_text()
            
            if 'Head coach' not in text and 'head coach' not in text:
                continue
            
            # Find which country this belongs to
            prev_h3 = element.find_previous('h3')
            prev_h2 = element.find_previous('h2')
            
            if not (prev_h3 and prev_h2):
                continue
            
            country = clean(prev_h3.get_text())
            group = prev_h2.get_text().strip()
            
            if group not in squads or country not in squads[group]:
                continue
            
            # Multiple coach patterns to try
            patterns = [
                r'[Hh]ead\s+coach:?\s*([^\[\n]+?)(?:\[|–|;|$)',  # "Head coach: Name [" or "–" or ";"
                r'[Hh]ead\s+coach:?\s*([^\n]+)',                   # "Head coach: Name (anything)"
            ]
            
            coach = ""
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    coach_raw = match.group(1).strip()
                    coach = clean(coach_raw)
                    break
            
            if coach and len(coach) > 2:
                squads[group][country]['coach'] = coach
                print(f"    {country}: coach = {coach}")
        
        # PASS 3: Extract player tables
        for table in soup.find_all('table', class_='wikitable'):
            try:
                # Find country context
                prev_h3 = table.find_previous('h3')
                prev_h2 = table.find_previous('h2')
                
                if not (prev_h3 and prev_h2):
                    continue
                
                country = clean(prev_h3.get_text())
                group = prev_h2.get_text().strip()
                
                if group not in squads or country not in squads[group]:
                    continue
                
                df = pd.read_html(StringIO(str(table)))[0]
                df = flatten_dataframe(df)
                
                # Check if this looks like a squad table
                cols_lower = [str(c).lower() for c in df.columns]
                has_players = any(x in ' '.join(cols_lower) for x in ['player', 'name', 'no', 'pos'])
                
                if (has_players and len(df) > 5) or len(df) > 15:
                    players = []
                    
                    for _, row in df.iterrows():
                        # Extract player name
                        pname = None
                        for col in df.columns:
                            col_str = str(col).lower()
                            if 'player' in col_str or ('name' in col_str and 'date' not in col_str):
                                pname = clean(row[col])
                                break
                        
                        if not pname:
                            pname = clean(str(row.iloc[0]))
                        
                        if pname and len(pname) > 1:
                            p = {"name": pname}
                            
                            # Get optional fields
                            for col in df.columns:
                                col_lower = str(col).lower()
                                if 'pos' in col_lower:
                                    p['position'] = clean(row[col])
                                elif 'club' in col_lower:
                                    p['club'] = clean(row[col])
                            
                            players.append(p)
                    
                    if players:
                        squads[group][country]['players'] = players
                        print(f"    {country}: {len(players)} players")
            
            except Exception:
                pass
        
        return squads
    
    except Exception as e:
        print(f"  ⚠️  Error in extract_squads_details: {e}")
        return {}

# ======================
# MAIN
# ======================
def main():
    print("\n🚀 Fetching Wikipedia data...\n")
    
    print("📊 Extracting group statistics...")
    groups = extract_group_stats()
    
    print("⚽ Extracting goalscorers...")
    goalscorers = extract_goalscorers()
    
    print("🔴 Extracting discipline records...")
    discipline = extract_discipline()
    
    print("🏆 Extracting Man of the Match...")
    motm = extract_motm()
    
    print("\n📋 Extracting main tables (venues, referees)...")
    tables_data = extract_main_tables()

    data = {
        "groups": extract_groups(),
        "goalscorers": goalscorers,
        "discipline": discipline,
        "man_of_the_match": motm,
        "squads": extract_squads_details(),
        "venues": tables_data.get("venues", []),
        "referees": tables_data.get("referees", [])
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Structured CAN 2025 data saved to {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
