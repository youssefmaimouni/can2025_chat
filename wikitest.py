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


def extract_qualified_teams():
    """Extract the Qualified teams table from the qualification page."""
    url = "https://en.wikipedia.org/wiki/2025_Africa_Cup_of_Nations_qualification"
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"  ⚠️  HTTP {resp.status_code} fetching qualification page")
            return []
        soup = BeautifulSoup(resp.text, "html.parser")

        # Try to find a section or span with "Qualified teams"
        qualified_table = None
        # look for section id first
        span = soup.find('span', id=lambda x: x and 'Qualified' in x)
        if span:
            header = span.find_parent(['h2', 'h3', 'h4'])
            if header:
                qualified_table = header.find_next('table')

        # fallback: search captions/tables with relevant header text
        if not qualified_table:
            for table in soup.find_all('table', class_='wikitable'):
                caption = table.find('caption')
                if caption and 'Qualified teams' in caption.get_text():
                    qualified_table = table
                    break

        # final fallback: any table that looks like a qualified teams table
        if not qualified_table:
            for table in soup.find_all('table', class_='wikitable'):
                try:
                    df = pd.read_html(StringIO(str(table)))[0]
                    df = flatten_dataframe(df)
                    cols = [c.lower() for c in df.columns]
                    if any('team' in c for c in cols) and any('qualified' in c or 'qualified on' in c or 'qualified as' in c for c in cols):
                        qualified_table = table
                        break
                except Exception:
                    continue

        if not qualified_table:
            print('  ⚠️  Qualified teams table not found')
            return []

        df = pd.read_html(StringIO(str(qualified_table)))[0]
        df = flatten_dataframe(df)
        # normalize columns
        df.columns = [str(c).strip() for c in df.columns]
        records = df.to_dict(orient='records')
        print(f"  ✅ Extracted Qualified teams ({len(records)} rows)")
        return records
    except Exception as e:
        print(f"  ⚠️  Error extracting qualified teams: {e}")
        return []


def extract_tournament_goalscorers():
    """Extract goalscorers from group stage matches with minutes and match context."""
    url = "https://en.wikipedia.org/wiki/2025_Africa_Cup_of_Nations"
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"  ⚠️  HTTP {resp.status_code} fetching tournament page")
            return []
        
        soup = BeautifulSoup(resp.text, "html.parser")
        results = []
        
        # Find the "Group stage" section first
        group_stage_heading = None
        for heading in soup.find_all(['h2', 'h3']):
            h_text = heading.get_text().strip()
            if 'Group stage' in h_text or 'group stage' in h_text.lower():
                group_stage_heading = heading
                break
        
        if not group_stage_heading:
            print("  ⚠️  Group stage section not found")
            return []
        
        print("  ✅ Found Group stage section")
        
        group_letters = ["A", "B", "C", "D", "E", "F"]
        
        # Process each group
        for letter in group_letters:
            # Find group heading (e.g., "Group A")
            group_heading = None
            for h in group_stage_heading.find_next_siblings(['h2', 'h3', 'h4']):
                h_text = h.get_text().strip()
                if f'Group {letter}' in h_text:
                    group_heading = h
                    break
                # Stop if we hit another major section
                if any(x in h_text.lower() for x in ['knockout', 'quarter', 'semi', 'final']):
                    break
            
            if not group_heading:
                continue
            
            print(f"    Processing Group {letter}...")
            
            # Find all match boxes for this group
            node = group_heading.next_sibling
            match_count = 0
            
            while node:
                # Stop at next group or major section
                if hasattr(node, 'name') and node.name in ['h2', 'h3', 'h4']:
                    node_text = node.get_text().strip()
                    if any(f'Group {l}' in node_text for l in group_letters) or \
                       any(x in node_text.lower() for x in ['knockout', 'quarter', 'semi', 'final']):
                        break
                
                # Look for match info patterns
                if hasattr(node, 'name') and node.name == 'div':
                    # Try to extract match and goalscorer info from text
                    node_text = node.get_text()
                    
                    # Look for score pattern: "Team1 X–Y Team2"
                    score_pattern = r'([A-Z][A-Za-z\s]+?)\s+(\d+)[–-](\d+)\s+([A-Z][A-Za-z\s]+?)(?:\n|$)'
                    score_match = re.search(score_pattern, node_text)
                    
                    if score_match:
                        home_team = clean(score_match.group(1))
                        score_h = score_match.group(2)
                        score_a = score_match.group(3)
                        away_team = clean(score_match.group(4))
                        match_score = f"{score_h}–{score_a}"
                        
                        # Look for goalscorer lines with minutes
                        # Pattern: PlayerName followed by minute(s)
                        lines = node_text.split('\n')
                        for line in lines:
                            line = line.strip()
                            if not line or len(line) < 3:
                                continue
                            
                            # Look for "PlayerName Minute'" pattern
                            goal_pattern = r'^([A-Z][a-z\s\'-]+?)\s+(\d{1,2})(?:\+(\d+))?[\'\"]?(?:\s|$)'
                            g_match = re.match(goal_pattern, line)
                            
                            if g_match:
                                player_raw = g_match.group(1).strip()
                                minute_val = g_match.group(2)
                                extra_min = g_match.group(3)
                                
                                if extra_min:
                                    minute = f"{minute_val}+{extra_min}"
                                else:
                                    minute = minute_val
                                
                                # Filter out non-player text
                                if any(x in player_raw.lower() for x in ['report', 'attendance', 'referee', 'match']):
                                    continue
                                
                                player = clean(player_raw)
                                if len(player) > 2:
                                    entry = {
                                        "group": f"Group {letter}",
                                        "match": f"{home_team} {match_score} {away_team}",
                                        "home_team": home_team,
                                        "away_team": away_team,
                                        "score": match_score,
                                        "player": player,
                                        "minute": minute
                                    }
                                    
                                    # Avoid duplicates
                                    if entry not in results:
                                        results.append(entry)
                                        print(f"      {home_team} {match_score} {away_team}: {player} ({minute}')")
                                        match_count += 1
                
                node = node.next_sibling
            
            print(f"      Found {match_count} goalscorer entries")
        
        if len(results) == 0:
            print("  ⚠️  No goalscorers found with team context")
        else:
            print(f"  ✅ Extracted {len(results)} tournament goalscorer records with match context")
        
        return results
    
    except Exception as e:
        print(f"  ⚠️  Error extracting tournament goalscorers: {e}")
        return []


def extract_qualification_goalscorers():
    """Extract goalscorers info from the qualification page - parses bullet list with country flags."""
    url = "https://en.wikipedia.org/wiki/2025_Africa_Cup_of_Nations_qualification"
    headers = {"User-Agent": USER_AGENT}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"  ⚠️  HTTP {resp.status_code} fetching qualification page")
            return []
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find heading containing "Goalscorer" or "Goalscorers"
        goals_heading = None
        for h in soup.find_all(['h2', 'h3', 'h4']):
            heading_text = h.get_text(strip=True).lower()
            if 'goalscorer' in heading_text:
                goals_heading = h
                print(f"  ✅ Found goalscorers heading: {heading_text}")
                break

        results = []
        if not goals_heading:
            print('  ⚠️  Goalscorers section not found on qualification page')
            return []

        # Collect all list items (li) after goalscorers heading until next h2/h3/h4
        current_goals = None
        current_country = None
        
        for element in goals_heading.find_next_siblings():
            if element.name in ['h2', 'h3', 'h4']:
                break
            
            # Skip non-structural elements
            if element.name not in ['ul', 'ol', 'li', 'p', 'strong', 'b']:
                continue
            
            text = element.get_text(strip=True)
            if not text:
                continue
            
            # Pattern: "X goals" header - sets goal count for following items
            goal_match = re.match(r'^(\d+)\s+goals?$', text, re.IGNORECASE)
            if goal_match:
                current_goals = int(goal_match.group(1))
                print(f"    Section: {current_goals} goals")
                continue
            
            # For list items, try to extract country and player
            if element.name == 'li':
                # Try to find country link (usually first link in the li)
                country_link = element.find('a')
                country_name = None
                
                if country_link:
                    # Get the link title or text
                    link_title = country_link.get('title', '')
                    if 'national football team' in link_title.lower():
                        # Extract country name from title like "Morocco national football team"
                        country_name = link_title.replace(' national football team', '').strip()
                    else:
                        country_name = country_link.get_text(strip=True)
                
                # Get player name - usually the text after the country link
                player_name = element.get_text(strip=True)
                
                # Remove country name from player text if it's there
                if country_name and player_name.startswith(country_name):
                    player_name = player_name[len(country_name):].strip()
                
                # Clean up player name - remove flag icons and special chars
                player_name = clean(player_name)
                
                if player_name and len(player_name) > 2:
                    entry = {
                        "country": country_name if country_name else "Unknown",
                        "player": player_name,
                        "goals": current_goals if current_goals else 1
                    }
                    results.append(entry)
                    print(f"    {country_name} - {player_name} ({current_goals} goals)")
        
        print(f"  ✅ Extracted {len(results)} qualification goalscorer records")
        return results
    except Exception as e:
        print(f"  ⚠️  Error extracting qualification goalscorers: {e}")
        import traceback
        traceback.print_exc()
        return []

def extract_goalscorers():
    """Extract goalscorers with goal counts from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/2025_Africa_Cup_of_Nations"
    headers = {"User-Agent": USER_AGENT}
    
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"  ⚠️  HTTP {resp.status_code} fetching tournament page")
            return []
        
        soup = BeautifulSoup(resp.text, "html.parser")
        goalscorers = []
        
        # Find "Goalscorers" or "Top scorers" heading
        goals_heading = None
        for heading in soup.find_all(['h2', 'h3', 'h4']):
            h_text = heading.get_text().strip().lower()
            if 'goalscorer' in h_text or 'top scorer' in h_text:
                goals_heading = heading
                print(f"  ✅ Found: {heading.get_text().strip()}")
                break
        
        if not goals_heading:
            print("  ⚠️  Goalscorers section not found")
            return []
        
        # Find the table after the heading
        table = goals_heading.find_next('table', class_='wikitable')
        
        if not table:
            print("  ⚠️  Goalscorers table not found")
            return []
        
        # Parse the table
        try:
            df = pd.read_html(StringIO(str(table)))[0]
            df = flatten_dataframe(df)
            
            # Get column names (case-insensitive)
            cols_lower = [str(c).lower() for c in df.columns]
            
            # Find player and goals columns
            player_col = None
            goals_col = None
            
            for i, col in enumerate(cols_lower):
                if 'player' in col or 'name' in col:
                    player_col = df.columns[i]
                elif 'goal' in col or 'score' in col:
                    goals_col = df.columns[i]
            
            if not player_col or not goals_col:
                print(f"  ⚠️  Could not find player or goals columns. Available: {list(df.columns)}")
                return []
            
            # Extract data
            for _, row in df.iterrows():
                player_raw = str(row[player_col]).strip()
                goals_raw = str(row[goals_col]).strip()
                
                player = clean(player_raw)
                
                # Extract goal count (handle different formats: "3", "3 goals", etc)
                goals = None
                try:
                    # Try to extract first number from the string
                    goals_match = re.search(r'(\d+)', goals_raw)
                    if goals_match:
                        goals = int(goals_match.group(1))
                except:
                    pass
                
                if player and len(player) > 2 and goals:
                    entry = {"player": player, "goals": goals}
                    goalscorers.append(entry)
                    print(f"       + {player} ({goals})")
            
            print(f"  📊 Total goalscorers extracted: {len(goalscorers)}")
            return goalscorers
        
        except Exception as e:
            print(f"  ⚠️  Error parsing goalscorers table: {e}")
            return []
    
    except Exception as e:
        print(f"  ⚠️  Error extracting goalscorers: {e}")
        return []

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
    
    print("\n📋 Extracting qualification page data...")
    qualified_teams = extract_qualified_teams()
    qual_goalscorers = extract_qualification_goalscorers()
    
    print("\n⚽ Extracting tournament group stage goalscorers...")
    tournament_goalscorers = extract_tournament_goalscorers()

    data = {
        "groups": extract_groups(),
        "goalscorers": goalscorers,
        "discipline": discipline,
        "man_of_the_match": motm,
        "squads": extract_squads_details(),
        "venues": tables_data.get("venues", []),
        "referees": tables_data.get("referees", []),
        "qualified_teams": qualified_teams,
        "qualification_goalscorers": qual_goalscorers,
        "tournament_goalscorers": tournament_goalscorers
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"✅ Structured CAN 2025 data saved to {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
