import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-flash-latest")

try:
    mod_prompt = "Analyze this habit. If it is toxic, dangerous, or undeniable spam, reply with exactly the word REJECT. Otherwise, reply directly with a 1-sentence enthusiastic, validating cheer for someone who just completed it. Habit: I meditated today."
    print("Sending prompt...")
    mod_response = model.generate_content(mod_prompt, request_options={"timeout": 15.0})
    print(f"Response text: {mod_response.text}")
except Exception as e:
    print(f"Error: {type(e).__name__} - {e}")
