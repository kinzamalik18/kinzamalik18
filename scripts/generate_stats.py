import os
import json
import urllib.request
import urllib.error
import base64
from datetime import datetime, timedelta, timezone

# Configuration
FONT_B64_FILE = "font_ui_b64.txt"
GITHUB_API_URL = "https://api.github.com/graphql"

def load_font_b64():
    if os.path.exists(FONT_B64_FILE):
        with open(FONT_B64_FILE, 'r') as f:
            return f.read().strip()
    print("Warning: font_ui_b64.txt not found. Font will not be embedded.")
    return ""

def run_graphql_query(query, variables, token):
    req = urllib.request.Request(
        GITHUB_API_URL,
        data=json.dumps({"query": query, "variables": variables}).encode("utf-8"),
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; Python stats generator)",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if "errors" in res_data:
                print(f"GraphQL Errors: {res_data['errors']}")
                return None
            return res_data.get("data")
    except urllib.error.URLError as e:
        print(f"HTTP Request failed: {e}")
        return None

def get_stats_data(username, token):
    # Pin window to whole UTC days to prevent shifting sparkline boundaries
    today = datetime.now(timezone.utc)
    to_date = today.replace(hour=23, minute=59, second=59, microsecond=0)
    from_date = (to_date - timedelta(days=364)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    from_str = from_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    to_str = to_date.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
                weekday
              }
            }
          }
        }
        repositories(ownerAffiliations: OWNER, first: 100, privacy: PUBLIC, isFork: false) {
          nodes {
            name
            languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
              edges {
                size
                node {
                  name
                  color
                }
              }
            }
          }
        }
      }
    }
    """
    
    variables = {
      "login": username,
      "from": from_str,
      "to": to_str
    }
    
    return run_graphql_query(query, variables, token)

def get_mock_data():
    print("Using MOCK DATA for local testing...")
    # Generate 52 weeks of dummy contributions
    weeks = []
    base_date = datetime.now(timezone.utc) - timedelta(days=364)
    total_contribs = 0
    
    # We will generate a nice streak
    # Let's say a 15 day current streak and 32 day longest streak
    for w in range(53):
        days = []
        for d in range(7):
            date_str = (base_date + timedelta(days=w*7 + d)).strftime("%Y-%m-%d")
            # Create realistic distribution: more on weekdays, some 0 days
            day_index = w*7 + d
            if day_index > 340 and day_index <= 355:
                # current streak days
                count = (day_index % 5) + 1
            elif day_index > 120 and day_index <= 152:
                # longest streak days
                count = (day_index % 6) + 1
            else:
                # general days
                count = 0 if (day_index % 3 == 0) else (day_index % 4)
            
            total_contribs += count
            days.append({
                "contributionCount": count,
                "date": date_str,
                "weekday": d
            })
        weeks.append({"contributionDays": days})
        
    return {
        "user": {
            "contributionsCollection": {
                "contributionCalendar": {
                    "totalContributions": total_contribs,
                    "weeks": weeks
                }
            },
            "repositories": {
                "nodes": [
                    {
                        "name": "project-1",
                        "languages": {
                            "edges": [
                                {"size": 45000, "node": {"name": "TypeScript", "color": "#3178c6"}},
                                {"size": 15000, "node": {"name": "HTML", "color": "#e34c26"}},
                                {"size": 10000, "node": {"name": "CSS", "color": "#563d7c"}}
                            ]
                        }
                    },
                    {
                        "name": "project-2",
                        "languages": {
                            "edges": [
                                {"size": 30000, "node": {"name": "TypeScript", "color": "#3178c6"}},
                                {"size": 25000, "node": {"name": "Python", "color": "#3572A5"}}
                            ]
                        }
                    }
                ]
            }
        }
    }

def calculate_streaks(weeks):
    all_days = []
    for week in weeks:
        for day in week["contributionDays"]:
            all_days.append(day)
            
    # Sort by date just to be safe
    all_days.sort(key=lambda x: x["date"])
    
    current_streak = 0
    longest_streak = 0
    
    current_start = None
    current_end = None
    longest_start = None
    longest_end = None
    
    temp_streak = 0
    temp_start = None
    
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    
    for i, day in enumerate(all_days):
        count = day["contributionCount"]
        date_str = day["date"]
        
        if count > 0:
            if temp_streak == 0:
                temp_start = date_str
            temp_streak += 1
            
            # Update longest streak
            if temp_streak > longest_streak:
                longest_streak = temp_streak
                longest_start = temp_start
                longest_end = date_str
        else:
            if temp_streak > 0:
                # streak ended
                temp_streak = 0
                
        # Check for current streak
        # A streak is current if it's active today or yesterday
        if date_str == today_str or date_str == yesterday_str:
            if count > 0 or (date_str == today_str and temp_streak > 0):
                current_streak = temp_streak
                current_start = temp_start
                current_end = date_str
                
    # Format date ranges nicely (e.g., "Oct 12 - Nov 25")
    def format_date_range(start_str, end_str):
        if not start_str or not end_str:
            return "N/A"
        try:
            start_dt = datetime.strptime(start_str, "%Y-%m-%d")
            end_dt = datetime.strptime(end_str, "%Y-%m-%d")
            
            # If same year as current, omit year
            curr_year = datetime.now().year
            if start_dt.year == curr_year and end_dt.year == curr_year:
                return f"{start_dt.strftime('%b %d')} - {end_dt.strftime('%b %d')}"
            return f"{start_dt.strftime('%b %d, %Y')} - {end_dt.strftime('%b %d, %Y')}"
        except Exception:
            return f"{start_str} to {end_str}"
            
    longest_range = format_date_range(longest_start, longest_end)
    current_range = format_date_range(current_start, current_end) if current_streak > 0 else "No active streak"
    
    return current_streak, current_range, longest_streak, longest_range

def aggregate_languages(repos_data):
    lang_bytes = {}
    lang_colors = {}
    
    for repo in repos_data.get("nodes", []):
        for edge in repo.get("languages", {}).get("edges", []):
            name = edge["node"]["name"]
            color = edge["node"]["color"] or "#858585"
            size = edge["size"]
            
            lang_bytes[name] = lang_bytes.get(name, 0) + size
            lang_colors[name] = color
            
    total_bytes = sum(lang_bytes.values())
    if total_bytes == 0:
        return []
        
    sorted_langs = sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)
    
    top_langs = []
    for name, size in sorted_langs[:5]:
        pct = (size / total_bytes) * 100
        top_langs.append({
            "name": name,
            "pct": pct,
            "color": lang_colors[name]
        })
        
    return top_langs

def generate_svg_header(width, height, font_b64):
    header = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%">',
        '  <defs>'
    ]
    if font_b64:
        header.append('    <style>')
        header.append('      @font-face {')
        header.append("        font-family: 'JetBrains Mono';")
        header.append(f"        src: url('{font_b64}') format('woff2');")
        header.append('        font-weight: normal;')
        header.append('        font-style: normal;')
        header.append('      }')
        header.append('    </style>')
        
    header.append('    <style>')
    header.append("      text { font-family: 'JetBrains Mono', monospace; font-size: 13px; fill: #c9d1d9; }")
    header.append("      .title { font-size: 11px; fill: #8b949e; letter-spacing: 1.5px; text-transform: uppercase; }")
    header.append("      .value { font-size: 24px; font-weight: bold; fill: #58a6ff; }")
    header.append("      .label { fill: #8b949e; }")
    header.append("      .sub { font-size: 11px; fill: #8b949e; }")
    header.append("      .accent { fill: #58a6ff; }")
    header.append("      .dim { fill: #30363d; }")
    header.append("      .bar-bg { fill: #21262d; rx: 3px; }")
    header.append('      @media (prefers-color-scheme: light) {')
    header.append("        text { fill: #24292f; }")
    header.append("        .title { fill: #57606a; }")
    header.append("        .value { fill: #0969da; }")
    header.append("        .label { fill: #57606a; }")
    header.append("        .sub { fill: #57606a; }")
    header.append("        .accent { fill: #0969da; }")
    header.append("        .dim { fill: #afb8c1; }")
    header.append("        .bar-bg { fill: #f6f8fa; }")
    header.append('      }')
    header.append('    </style>')
    header.append('  </defs>')
    return header

def draw_stats_svg(total_contribs, weeks, font_b64):
    # Calculate weekly counts
    weekly_counts = []
    for week in weeks:
        weekly_sum = sum(day["contributionCount"] for day in week["contributionDays"])
        weekly_counts.append(weekly_sum)
        
    # Scale sparkline
    max_weekly = max(weekly_counts) if max(weekly_counts) > 0 else 1
    
    svg = generate_svg_header(460, 110, font_b64)
    
    # Title
    svg.append('  <text x="15" y="25" class="title">CONTRIBUTIONS</text>')
    
    # Hero number
    svg.append(f'  <text x="15" y="60" class="value">{total_contribs:,}</text>')
    svg.append('  <text x="15" y="80" class="sub">Total in the past year</text>')
    
    # Sparkline (52 columns on the right side)
    # Right side starts at x = 200, width = 240px
    spark_x = 200
    spark_y = 80
    spark_h = 55
    col_w = 3.5
    gap = 1.0
    
    svg.append('  <!-- Sparkline -->')
    for i, count in enumerate(weekly_counts[-52:]):  # Make sure we only show last 52 weeks
        h = max(1.5, (count / max_weekly) * spark_h)
        x = spark_x + i * (col_w + gap)
        y = spark_y - h
        
        # Color intensity based on count
        if count == 0:
            svg.append(f'    <rect x="{x:.1f}" y="{spark_y-1.5:.1f}" width="{col_w}" height="1.5" class="dim" rx="0.5" />')
        else:
            svg.append(f'    <rect x="{x:.1f}" y="{y:.1f}" width="{col_w}" height="{h:.1f}" class="accent" rx="0.5" />')
            
    svg.append('</svg>')
    
    with open("stats.svg", 'w', encoding='utf-8') as f:
        f.write("\n".join(svg))
    print("Generated stats.svg")

def draw_streak_svg(current_streak, current_range, longest_streak, longest_range, font_b64):
    svg = generate_svg_header(460, 110, font_b64)
    
    # Title
    svg.append('  <text x="15" y="25" class="title">STREAKS</text>')
    
    # Current Streak
    svg.append('  <g transform="translate(15, 40)">')
    svg.append('    <text x="0" y="15" class="sub">Current Streak</text>')
    svg.append(f'    <text x="0" y="42" class="value">{current_streak} days</text>')
    svg.append(f'    <text x="0" y="58" class="sub">{current_range}</text>')
    svg.append('  </g>')
    
    # Longest Streak
    svg.append('  <g transform="translate(240, 40)">')
    svg.append('    <text x="0" y="15" class="sub">Longest Streak</text>')
    svg.append(f'    <text x="0" y="42" class="value">{longest_streak} days</text>')
    svg.append(f'    <text x="0" y="58" class="sub">{longest_range}</text>')
    svg.append('  </g>')
    
    svg.append('</svg>')
    
    with open("streak.svg", 'w', encoding='utf-8') as f:
        f.write("\n".join(svg))
    print("Generated streak.svg")

def draw_langs_svg(langs, font_b64):
    svg = generate_svg_header(460, 140, font_b64)
    
    # Title
    svg.append('  <text x="15" y="25" class="title">TOP LANGUAGES</text>')
    
    if not langs:
        svg.append('  <text x="15" y="65" class="sub">No public repositories language data found.</text>')
    else:
        # 1. ProgressBar bar stack
        # Width = 430px, x = 15, y = 45, h = 10
        svg.append('  <!-- Language Progress Bar -->')
        curr_x = 15.0
        bar_w = 430.0
        bar_h = 10.0
        
        # We need a clip path or rx for rounded ends. 
        # Easier: draw a background card and clip.
        svg.append(f'  <mask id="bar-mask"><rect x="15" y="45" width="{bar_w}" height="{bar_h}" rx="5" fill="white" /></mask>')
        
        for lang in langs:
            w = (lang["pct"] / 100) * bar_w
            svg.append(f'  <rect x="{curr_x:.1f}" y="45" width="{w:.1f}" height="{bar_h}" fill="{lang["color"]}" mask="url(#bar-mask)" />')
            curr_x += w
            
        # 2. Legend (Columns / Rows)
        # We lay out 5 items. 3 in first row (y=80), 2 in second row (y=105).
        # x coordinates:
        # Col 0: 15, Col 1: 160, Col 2: 300
        legend_positions = [
            (15, 80), (160, 80), (305, 80),
            (15, 105), (160, 105)
        ]
        
        svg.append('  <!-- Legend -->')
        for i, lang in enumerate(langs):
            x, y = legend_positions[i]
            # Color dot
            svg.append(f'  <circle cx="{x+6}" cy="{y-4}" r="5" fill="{lang["color"]}" />')
            # Text name and percent
            svg.append(f'  <text x="{x+18}" y="{y}">{lang["name"]} <tspan class="sub">{lang["pct"]:.1f}%</tspan></text>')
            
    svg.append('</svg>')
    
    with open("langs.svg", 'w', encoding='utf-8') as f:
        f.write("\n".join(svg))
    print("Generated langs.svg")

def draw_year_svg(weeks, font_b64):
    # Setup character ramp (same as portrait)
    ramp = " .`:-=+*cs#%@"
    
    # We want a 53 column (weeks) x 7 row (days) grid
    # Let's extract counts for each week and weekday
    # weeks is a list of weeks, where each week contains contributionDays (length <= 7)
    # Let's form a grid of 7 rows x 53 columns
    grid = [[0 for _ in range(53)] for _ in range(7)]
    
    # Find max daily count to scale character selection
    max_daily = 0
    for w_idx, week in enumerate(weeks[-53:]):  # Limit to last 53 weeks
        for day in week["contributionDays"]:
            weekday = day["weekday"]  # 0 is Sunday, 6 is Saturday
            count = day["contributionCount"]
            if count > max_daily:
                max_daily = count
                
    if max_daily == 0:
        max_daily = 1
        
    for w_idx, week in enumerate(weeks[-53:]):
        for day in week["contributionDays"]:
            weekday = day["weekday"]
            count = day["contributionCount"]
            grid[weekday][w_idx] = count
            
    svg = generate_svg_header(460, 150, font_b64)
    
    # Title
    svg.append('  <text x="15" y="25" class="title">YEAR IN REVIEW</text>')
    
    # Grid of characters
    # Left edge starts at x=35.
    # Spacing between columns = 7.74px (char width)
    # Spacing between rows = 13.0px
    # Weekday labels on the left: M, W, F (at rows 1, 3, 5)
    labels = {1: "M", 3: "W", 5: "F"}
    for row_idx, label in labels.items():
        svg.append(f'  <text x="15" y="{45 + row_idx * 13 + 10}" class="sub">{label}</text>')
        
    # Draw character cells
    svg.append('  <!-- Character Grid -->')
    for row in range(7):
        y = 45 + row * 13 + 10
        row_chars = []
        for col in range(53):
            val = grid[row][col]
            if val == 0:
                idx = 0  # maps to space ' ' (invisible) or let's use '.' for zero? 
                # To make it look like a grid, using '.' is much better than empty space.
                # Actually, the ramp's second char is '.', which is very subtle.
                # If we use '.' for 0, and then scale the rest from 1 to 12.
                char = '.'
            else:
                # Map 1 to max_daily to index 1 to 12 in the ramp
                idx = 1 + int((val - 1) / max_daily * (len(ramp) - 2))
                idx = min(len(ramp) - 1, max(1, idx))
                char = ramp[idx]
            row_chars.append(char)
            
        row_str = "".join(row_chars)
        # Escape XML entities just in case
        row_str_escaped = row_str.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        # Write the whole line of characters as one text block for high rendering efficiency
        svg.append(f'  <text x="40" y="{y}" style="font-family: \'JetBrains Mono\', monospace; white-space: pre;">{row_str_escaped}</text>')
        
    svg.append('</svg>')
    
    with open("year.svg", 'w', encoding='utf-8') as f:
        f.write("\n".join(svg))
    print("Generated year.svg")

def main():
    username = os.environ.get("GH_LOGIN")
    token = os.environ.get("GITHUB_TOKEN")
    
    if not username or not token:
        print("Missing GH_LOGIN or GITHUB_TOKEN environment variables.")
        # Try to read username from git config
        username = "kinzamalik18"
        data = get_mock_data()
    else:
        print(f"Fetching GitHub stats for user {username}...")
        data = get_stats_data(username, token)
        if not data:
            print("Failed to fetch data from API. Falling back to mock data.")
            data = get_mock_data()
            
    user_data = data.get("user", {})
    contrib_collection = user_data.get("contributionsCollection", {})
    calendar = contrib_collection.get("contributionCalendar", {})
    
    total_contribs = calendar.get("totalContributions", 0)
    weeks = calendar.get("weeks", [])
    repos_data = user_data.get("repositories", {})
    
    current_streak, current_range, longest_streak, longest_range = calculate_streaks(weeks)
    langs = aggregate_languages(repos_data)
    
    font_b64 = load_font_b64()
    
    draw_stats_svg(total_contribs, weeks, font_b64)
    draw_streak_svg(current_streak, current_range, longest_streak, longest_range, font_b64)
    draw_langs_svg(langs, font_b64)
    draw_year_svg(weeks, font_b64)
    
if __name__ == "__main__":
    main()
