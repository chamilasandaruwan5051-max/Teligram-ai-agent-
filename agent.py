import os
import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import telebot
import google.generativeai as genai

# --- Dummy HTTP Server for Render Free Web Service ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# Start dummy HTTP server in background
threading.Thread(target=run_health_server, daemon=True).start()

# --- BOT CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)
bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

MEMORY_FILE = "agent_memory.json"

# Active stable Gemini model names to try sequentially
CANDIDATE_MODELS = [
    'gemini-1.5-flash-latest',
    'gemini-1.5-flash',
    'gemini-1.5-pro-latest',
    'gemini-1.5-pro'
]

def generate_response(prompt):
    """Try stable Gemini model versions cleanly without extra model prefixes."""
    last_error = None
    for raw_name in CANDIDATE_MODELS:
        clean_name = raw_name.replace('models/', '')
        try:
            model = genai.GenerativeModel(clean_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            last_error = e
            continue

    raise Exception(f"No working Gemini model found. Last error: {last_error}")

def load_memory():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "system_instructions": "You are a helpful, self-improving AI agent connected via Telegram.",
        "learned_facts": []
    }

def save_memory(memory_data):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory_data, f, ensure_ascii=False, indent=4)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = (
        "ආයුබෝවන්! මම Cloud එකේ 24/7 දිවෙන ඔබේ AI Agent.\n\n"
        "1. /learn <උපදෙස> - මගේ මතකයට අලුත් දෙයක් එකතු කරන්න.\n"
        "2. /memory - මගේ මතකය පරීක්ෂා කරන්න.\n"
        "3. ඕනෑම ප්‍රශ්නයක් කෙළින්ම ඇසීමට හැකිය."
    )
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['memory'])
def show_memory(message):
    memory = load_memory()
    facts = "\n- ".join(memory["learned_facts"]) if memory["learned_facts"] else "තවම විශේෂ මතකයන් නැත."
    bot.reply_to(message, f"**Agent Memory:**\n- {facts}", parse_mode="Markdown")

@bot.message_handler(commands=['learn'])
def learn_instruction(message):
    instruction = message.text.replace('/learn', '').strip()
    if not instruction:
        bot.reply_to(message, "උපදෙසක් ලබා දෙන්න. උදා: `/learn පිළිතුරු සිංහලෙන් දෙන්න.`", parse_mode="Markdown")
        return
    
    memory = load_memory()
    memory["learned_facts"].append(instruction)
    save_memory(memory)
    bot.reply_to(message, f"මතක තබා ගත්තා: '{instruction}'")

@bot.message_handler(func=lambda message: True)
def handle_chat(message):
    memory = load_memory()
    context_prompt = f"System Instruction: {memory['system_instructions']}\nLearned Facts:\n"
    for fact in memory["learned_facts"]:
        context_prompt += f"- {fact}\n"
        
    full_prompt = f"{context_prompt}\nUser Question: {message.text}\nResponse:"
    
    try:
        reply_text = generate_response(full_prompt)
        bot.reply_to(message, reply_text)
    except Exception as e:
        bot.reply_to(message, f"දෝෂයක් සිදු විය: {str(e)}")

if __name__ == "__main__":
    print("Agent is running on Cloud...")
    # Clear any active webhooks or lingering polling instances
    try:
        bot.remove_webhook()
        time.sleep(1)
    except Exception as e:
        print(f"Webhook cleanup note: {e}")

    bot.infinity_polling(skip_pending_updates=True)
