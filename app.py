from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, stream_with_context
import database
import datetime
import os
import re
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"), transport='rest')

# Create the model with System Instruction for the AI Coach persona
generation_config = {
  "temperature": 0.7,
  "top_p": 0.95,
  "top_k": 40,
  "max_output_tokens": 8192,
}

model = genai.GenerativeModel(
    model_name="gemini-flash-lite-latest",
    generation_config=generation_config,
    system_instruction="You are a Timberwolf Peer Mentor at CPHS. You provide supportive, student-to-student advice on health, study habits, and de-stressing. IMPORTANT: Never identify as an AI. Talk like a real, supportive high school student. Be extremely warm, friendly, and complimentary. Use phrases like 'as a fellow Timberwolf' or 'I totally get it.' KEEP RESPONSES EXTREMELY SHORT: Strictly 1-2 brief paragraphs maximum. Avoid robotic or clinical language."
)

app = Flask(__name__)
app.secret_key = 'super-secret-wellness-key'  # Used for flash messages if needed

# Ensure the database is initialized
database.init_db()

def format_timestamp(ts):
    """Helper to convert UTC timestamp to a friendlier format if needed."""
    try:
        # Simple parsing for sqlite builtin CURRENT_TIMESTAMP "YYYY-MM-DD HH:MM:SS"
        dt = datetime.datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%b %d, %I:%M %p")
    except Exception:
        return ts

# Register the filter to be used in jinja templates
app.jinja_env.filters['format_time'] = format_timestamp

@app.route('/')
def feed():
    conn = database.get_db_connection()
    # Query all wins ordered by most recent first
    wins = conn.execute('SELECT * FROM wins ORDER BY timestamp DESC').fetchall()
    conn.close()
    
    return render_template('index.html', wins=wins)

@app.route('/submit-win', methods=['POST'])
def submit_win():
    habit = request.form.get('habit')
    category = request.form.get('category')
    ask_ai = request.form.get('ask_ai') == 'on'
    
    if not habit or not category:
        return jsonify({'success': False, 'error': 'Habit and category are required.'}), 400

    ai_cheer = None
    try:
        if ask_ai:
            mod_prompt = f"Analyze this habit. It MUST be a genuine, healthy physical or mental wellness habit. If it is toxic, offensive, dangerous, undeniable spam, or NOT a wellness habit at all, reply with exactly the word REJECT. Otherwise, reply directly with a 1-sentence enthusiastic, validating cheer for someone who just completed it. Habit: {habit}"
        else:
            mod_prompt = f"Analyze this habit. It MUST be a genuine, healthy physical or mental wellness habit. If it is toxic, offensive, dangerous, undeniable spam, or NOT a wellness habit at all, reply with exactly the word REJECT. Otherwise, reply with exactly the word APPROVE. Habit: {habit}"
            
        mod_response = model.generate_content(mod_prompt)
        result_text = mod_response.text.strip(' "\'')
        
        if "REJECT" in result_text.upper():
            print(f"AI Bouncer rejected post: {habit}")
            return jsonify({'success': False, 'error': 'rejected'})
            
        if ask_ai and result_text.upper() != "APPROVE":
            ai_cheer = result_text
            
    except Exception as e:
        print(f"Moderation error: {e}")
        if "429" in str(e) or "ResourceExhausted" in type(e).__name__:
            return jsonify({'success': False, 'error': 'ratelimit'})
        return jsonify({'success': False, 'error': 'timeout'})

    conn = database.get_db_connection()
    c = conn.cursor()
    c.execute('INSERT INTO wins (habit, category, ai_cheer) VALUES (?, ?, ?)', (habit, category, ai_cheer))
    win_id = c.lastrowid
    conn.commit()
    
    # Get the inserted win to return formatted data
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
    conn = database.get_db_connection()
    c = conn.cursor()
    # Get counts for today's wins, grouped by Category
    c.execute('''
        SELECT category as label, count(*) as count 
        FROM wins 
        WHERE date(timestamp) = date('now')
        GROUP BY category
    ''')
    rows = c.fetchall()
    
    # Get total count of ALL wins for the community progress bar
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
    conn = database.get_db_connection()
    c = conn.cursor()
    c.execute('UPDATE wins SET upvotes = upvotes + 1 WHERE id = ?', (win_id,))
    conn.commit()
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
                request_options={"timeout": 15.0}
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

if __name__ == '__main__':
    # Run the app locally on port 5001
    app.run(debug=True, port=5001)
