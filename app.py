from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, stream_with_context
import database
import datetime
import os
import re
import threading
import time
import requests as http_requests
import google.generativeai as genai
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

def is_offensive(text):
    """
    Local guardrail to catch obvious slurs and common character-substitution bypasses.
    Returns True if offensive patterns are detected.
    """
    if not text:
        return False
        
    # Standard character substitutions to check for
    subs = {
        'a': '[a4@]',
        'e': '[e3]',
        'i': '[i1!|]',
        'o': '[o0]',
        's': '[s5$]',
        'n': '[nv]', # Catching the specific bypass found today
        'g': '[g9]',
        't': '[t7]'
    }
    
    # Critical patterns (obfuscated here to catch obfuscated input)
    # This list is specifically designed to catch the slur variation identified by the user
    # and other common high-risk patterns.
    patterns = [
        # Variation of the N-word found (e.g., vigga, n1gga, etc)
        f"{subs['n']}{subs['i']}{subs['g']}{subs['g']}{subs['a']}",
        # Add other high-risk patterns here as needed
        r'\b[f|][u|*][c|k][k|]\b', # Basic profanity
    ]
    
    clean_text = text.lower().strip()
    for pattern in patterns:
        if re.search(pattern, clean_text, re.IGNORECASE):
            return True
    return False

# Create the model with System Instruction for the AI Coach persona
generation_config = {
  "temperature": 0.7,
  "top_p": 0.95,
  "top_k": 40,
  "max_output_tokens": 8192,
}

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash-lite",
    generation_config=generation_config,
    system_instruction=(
        "You are a Timberwolf Peer Mentor at CPHS. You provide supportive, student-to-student advice. "
        "CRITICAL SAFETY RULE: You are also a moderator. If the user input contains ANY slurs, "
        "profanity, leetspeak, or character substitutions meant to bypass filters, you MUST reject it. "
        "If the input is nonsense, ambiguous, or not clearly a positive wellness habit, you MUST reject it. "
        "Talk like a real high school student, but keep it clean and safe. "
        "KEEP RESPONSES EXTREMELY SHORT: Strictly 1-2 brief paragraphs maximum."
    )
)

app = Flask(__name__)
app.secret_key = 'super-secret-wellness-key'  # Used for flash messages if needed

# Ensure the database is initialized
database.init_db()

def format_timestamp(ts):
    """Helper to convert UTC timestamp to a friendlier format."""
    try:
        # Postgres returns datetime objects, SQLite returns strings
        if isinstance(ts, str):
            dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        else:
            dt = ts
        # Shift -5 hours for Central Time
        dt = dt - datetime.timedelta(hours=5)
        return dt.strftime("%b %d, %I:%M %p")
    except Exception:
        return str(ts)

# Register the filter to be used in jinja templates
app.jinja_env.filters['format_time'] = format_timestamp

@app.route('/')
def feed():
    conn, db_type = database.get_db_connection()
    if db_type == "postgres":
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM wins ORDER BY timestamp DESC')
        wins = cursor.fetchall()
    else:
        wins = conn.execute('SELECT * FROM wins ORDER BY timestamp DESC').fetchall()
    conn.close()
    
    # Dynamic Daily Mission based on day of week
    missions = {
        0: {"category": "Movement", "icon": "fa-person-running", "title": "Movement Monday", "desc": "Get your body moving! Share a Movement habit today."},
        1: {"category": "Hydration", "icon": "fa-droplet", "title": "Hydration Tuesday", "desc": "Stay hydrated! Share a Hydration habit today."},
        2: {"category": "Mindfulness", "icon": "fa-brain", "title": "Mindful Wednesday", "desc": "Find your focus. Share a Mindfulness habit today."},
        3: {"category": "Nutrition", "icon": "fa-apple-whole", "title": "Nutrition Thursday", "desc": "Fuel your body right! Share a Nutrition habit today."},
        4: {"category": "Sleep", "icon": "fa-moon", "title": "Sleep Friday", "desc": "Rest up for the weekend! Share a Sleep habit today."},
        5: {"category": "Digital Detox", "icon": "fa-power-off", "title": "Digital Detox Saturday", "desc": "Unplug and recharge. Share a Digital Detox habit!"},
        6: {"category": "Mindfulness", "icon": "fa-spa", "title": "Self-Care Sunday", "desc": "Take care of yourself. Share any wellness habit today!"},
    }
    today_local = datetime.datetime.now() - datetime.timedelta(hours=5)
    today = today_local.weekday()
    mission = missions.get(today, missions[0])
    
    return render_template('index.html', wins=wins, mission=mission)

@app.route('/resources')
def resources():
    return render_template('resources.html')

@app.route('/submit-win', methods=['POST'])
def submit_win():
    habit = request.form.get('habit')
    ask_ai = request.form.get('ask_ai') == 'on'
    
    if not habit:
        return jsonify({'success': False, 'error': 'Habit is required.'}), 400

    # Level 1: Local Keyword/Regex Filter
    if is_offensive(habit):
        print(f"Local Filter blocked post: {habit}")
        return jsonify({'success': False, 'error': 'rejected'})

    ai_cheer = None
    category = 'Movement'  # Default fallback
    
    # Valid categories the AI can assign
    valid_categories = ['Movement', 'Sleep', 'Hydration', 'Mindfulness', 'Nutrition', 'Digital Detox']
    
    try:
        # Level 2: Hardened AI Bouncer + Auto-Categorizer
        category_instruction = (
            "Analyze this habit. It MUST be a genuine, healthy physical or mental wellness habit. "
            "If it is toxic, offensive, dangerous, undeniable spam, or NOT a wellness habit at all, "
            "reply with exactly the word REJECT. Also REJECT if it uses character substitutions (leetspeak) "
            "to sneak in bad words. If it is ambiguous or nonsense, REJECT. "
            "If the habit IS valid, you must also classify it into exactly one of these categories: "
            "Movement, Sleep, Hydration, Mindfulness, Nutrition, Digital Detox. "
        )
        
        if ask_ai:
            mod_prompt = category_instruction + (
                "Reply in this exact format: CATEGORY|your 1-sentence enthusiastic cheer. "
                "Example: Hydration|Amazing job staying hydrated today! "
                f"Habit: {habit}"
            )
        else:
            mod_prompt = category_instruction + (
                "Reply in this exact format: CATEGORY "
                "Example: Hydration "
                f"Habit: {habit}"
            )
            
        mod_response = model.generate_content(mod_prompt)
        result_text = mod_response.text.strip(' "\'\n')
        
        if "REJECT" in result_text.upper():
            print(f"AI Bouncer rejected post: {habit}")
            return jsonify({'success': False, 'error': 'rejected'})
        
        if ask_ai and '|' in result_text:
            # Parse: "Category|Cheer text"
            parts = result_text.split('|', 1)
            ai_category = parts[0].strip()
            ai_cheer = parts[1].strip() if len(parts) > 1 else None
            
            # Validate category
            for vc in valid_categories:
                if vc.lower() == ai_category.lower():
                    category = vc
                    break
            
            # Clean up cheer
            if ai_cheer:
                ai_cheer = re.sub(r'(?i)^APPROVE[\s\.\!\-\:]*', '', ai_cheer).strip()
            if not ai_cheer:
                ai_cheer = "Great job on your wellness habit!"
        else:
            # No cheer requested — result is just the category name
            ai_category = result_text.strip()
            for vc in valid_categories:
                if vc.lower() == ai_category.lower():
                    category = vc
                    break
            
    except Exception as e:
        print(f"Moderation error: {e}")
        if "429" in str(e) or "ResourceExhausted" in type(e).__name__:
            return jsonify({'success': False, 'error': 'ratelimit'})
        return jsonify({'success': False, 'error': 'timeout'})

    conn, db_type = database.get_db_connection()
    c = conn.cursor()
    
    if db_type == "postgres":
        c.execute('INSERT INTO wins (habit, category, ai_cheer) VALUES (%s, %s, %s) RETURNING id', (habit, category, ai_cheer))
        win_id = c.fetchone()[0]
    else:
        c.execute('INSERT INTO wins (habit, category, ai_cheer) VALUES (?, ?, ?)', (habit, category, ai_cheer))
        win_id = c.lastrowid
        
    conn.commit()
    
    # Get the inserted win to return formatted data
    if db_type == "postgres":
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute('SELECT * FROM wins WHERE id = %s', (win_id,))
        win = c.fetchone()
    else:
        win = conn.execute('SELECT * FROM wins WHERE id = ?', (win_id,)).fetchone()
        
    conn.close()
    
    return jsonify({
        'success': True,
        'win': {
            'id': win['id'],
            'habit': win['habit'],
            'category': win['category'],
            'timestamp': format_timestamp(win['timestamp']),
            'upvotes': win['upvotes'],
            'ai_cheer': win['ai_cheer']
        }
    })

@app.route('/api/chart-data', methods=['GET'])
def chart_data():
    conn, db_type = database.get_db_connection()
    if db_type == "postgres":
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute('''
            SELECT category as label, count(*) as count 
            FROM wins 
            WHERE DATE(timestamp) = CURRENT_DATE
            GROUP BY category
        ''')
    else:
        c = conn.cursor()
        c.execute('''
            SELECT category as label, count(*) as count 
            FROM wins 
            WHERE date(timestamp) = date('now')
            GROUP BY category
        ''')
    rows = c.fetchall()
    
    # Get total count of ALL wins for the community progress bar
    if db_type == "postgres":
        c.execute('SELECT COUNT(*) as total FROM wins')
        total_count = c.fetchone()['total']
    else:
        # SQLite
        c.execute('SELECT COUNT(*) as total FROM wins')
        total_count = c.fetchone()['total']
    
    conn.close()
    
    # Format for Chart.js
    labels = [row['label'] for row in rows]
    data = [row['count'] for row in rows]
    
    return jsonify({
        'labels': labels, 
        'data': data,
        'total_count': total_count
    })

@app.route('/upvote/<int:win_id>', methods=['POST'])
def upvote_win(win_id):
    conn, db_type = database.get_db_connection()
    c = conn.cursor()
    placeholder = "%s" if db_type == "postgres" else "?"
    c.execute(f'UPDATE wins SET upvotes = upvotes + 1 WHERE id = {placeholder}', (win_id,))
    conn.commit()
    
    if db_type == "postgres":
        c = conn.cursor(cursor_factory=RealDictCursor)
        c.execute('SELECT upvotes FROM wins WHERE id = %s', (win_id,))
        new_upvotes = c.fetchone()['upvotes']
    else:
        c.execute('SELECT upvotes FROM wins WHERE id = ?', (win_id,))
        new_upvotes = c.fetchone()['upvotes']
        
    conn.close()
    return jsonify({'success': True, 'upvotes': new_upvotes})

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json()
    user_message = data.get('message', '')
    history = data.get('history', [])
    
    # Safety Filter
    crisis_keywords = r'\b(suicide|kill|hurt myself|cutting|die|self-harm|self harm|end it)\b'
    if re.search(crisis_keywords, user_message, re.IGNORECASE):
        crisis_response = "It sounds like you're going through a lot. Please reach out to the CPHS Counseling Team at 512-570-1223 or text the Crisis Text Line at 741741."
        def generate_crisis():
            import json
            yield f"data: {json.dumps({'text': crisis_response})}\n\n"
        return Response(stream_with_context(generate_crisis()), mimetype='text/event-stream')
        
    def generate():
        import json
        try:
            # Initialize a chat session with history
            chat_session = model.start_chat(history=history)
            
            # Generate the response with a 15-second timeout and stream=True
            response = chat_session.send_message(
                user_message, 
                stream=True,
                request_options={"timeout": 30.0}
            )
            for chunk in response:
                if chunk.text:
                    payload = json.dumps({"text": chunk.text})
                    yield f"data: {payload}\n\n"
        except Exception as e:
            print(f"Error calling Gemini: {e}")
            error_payload = json.dumps({"text": "I'm having trouble connecting right now, but remember to take a deep breath and drink some water!"})
            yield f"data: {error_payload}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/health')
def health():
    """Lightweight health-check endpoint used by the keep-alive pinger."""
    return 'OK', 200


# --------------- Keep-Alive Self-Ping ---------------
def keep_alive():
    """
    Background thread that pings our own /health endpoint every 14 minutes
    to prevent Render's free-tier from spinning down after 15 min of inactivity.
    Only runs when RENDER_EXTERNAL_URL is set (i.e. on Render, not locally).
    """
    url = os.getenv('RENDER_EXTERNAL_URL')
    if not url:
        return  # Not on Render, nothing to do
    ping_url = f"{url}/health"
    while True:
        time.sleep(14 * 60)  # 14 minutes
        try:
            http_requests.get(ping_url, timeout=10)
            print(f"[keep-alive] pinged {ping_url}")
        except Exception as e:
            print(f"[keep-alive] ping failed: {e}")


# Start the keep-alive thread only on Render
if os.getenv('RENDER_EXTERNAL_URL'):
    pinger = threading.Thread(target=keep_alive, daemon=True)
    pinger.start()
    print("[keep-alive] background pinger started")


if __name__ == '__main__':
    # Run the app locally on port 5001
    app.run(debug=True, port=5001)
