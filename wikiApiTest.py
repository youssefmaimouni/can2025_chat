import wikipediaapi

wiki = wikipediaapi.Wikipedia(
    user_agent='MyFootballBot/1.0 (contact@example.com)',
    language='en',
    extract_format=wikipediaapi.ExtractFormat.WIKI
)

pages = [
    "2025_Africa_Cup_of_Nations",
    "2025_Africa_Cup_of_Nations_squads",
    "2025_Africa_Cup_of_Nations_qualification",
    "African_Cup_of_Nations",
    "Morocco_national_football_team",
]

def print_sections(sections, level=0):
    """
    Recursively print sections and sub-sections
    """
    for section in sections:
        indent = "  " * level
        print(f"{indent}- Section: {section.title}")

        # Recursive call for sub-sections
        if section.sections:
            print_sections(section.sections, level + 1)

for p in pages:
    print(f"\nProcessing page: {p}")
    page = wiki.page(p)

    if not page.exists():
        print(f"Page {p} does not exist.")
        continue

    print_sections(page.sections)
