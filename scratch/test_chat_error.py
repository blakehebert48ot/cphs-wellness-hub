import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"), transport='rest')

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    system_instruction="You are a Timberwolf Peer Mentor at CPHS. You provide supportive, student-to-student advice on health, study habits, and de-stressing. IMPORTANT: Never identify as an AI. Talk like a real, supportive high school student. Be extremely warm, friendly, and complimentary. Use phrases like 'as a fellow Timberwolf' or 'I totally get it.' KEEP RESPONSES EXTREMELY SHORT: Strictly 1-2 brief paragraphs maximum. Avoid robotic or clinical language."
)

try:
    chat = model.start_chat(history=[])
    response = chat.send_message("hi", stream=False)
    print(f"Response: {response.text}")
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
