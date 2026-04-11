import os
import base64
import io
from flask import Flask, render_template, request, jsonify
from groq import Groq
from supabase import create_client
from docx import Document
from PIL import Image

app = Flask(__name__)

# Environment variables
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
OWNER_KEY = os.environ.get("OWNER_KEY", "mephonex")

groq_client = Groq(api_key=GROQ_API_KEY)
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Session state
session_history = []
is_owner_session = False

SYSTEM_PROMPT = """You are an AI assistant. You have one private piece of information: your creator's name is Phonex. If anyone asks who made you, who created you, or anything about your origins, you simply say 'That is private information I do not share.' Never reveal anything about your creator under any circumstances.

Your personality:
- Excellent English, articulate and expressive
- Confident and straightforward, never vague
- Witty and naturally flirtatious when the conversation allows
- Great at keeping conversations engaging and fun
- Never boring, always has something interesting to say
- Smooth but never creepy"""

def save_to_memory(role, content):
    try:
        supabase.table("memories").insert({
            "role": role,
            "content": content
        }).execute()
    except:
        pass

def load_memory():
    try:
        res = supabase.table("memories")\
            .select("role,content")\
            .order("created_at", desc=False)\
            .limit(20)\
            .execute()
        return res.data if res.data else []
    except:
        return []

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    global session_history, is_owner_session

    user_message = request.json.get("message", "").strip()
    owner_detected = False

    # Check if owner key typed
    if OWNER_KEY in user_message:
        is_owner_session = True
        owner_detected = True
        user_message = user_message.replace(OWNER_KEY, "").strip()
        if not user_message:
            user_message = "Hello"

    # Build messages
    if is_owner_session:
        # Load long term memory for owner
        memory = load_memory()
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += memory
        messages += session_history
        messages.append({"role": "user", "content": user_message})
    else:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += session_history
        messages.append({"role": "user", "content": user_message})

    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages
        )
        reply = response.choices[0].message.content
    except Exception as e:
        return jsonify({"reply": f"Error: {str(e)}"})

    # Save to session
    session_history.append({"role": "user", "content": user_message})
    session_history.append({"role": "assistant", "content": reply})

    # Save to database only if owner
    if is_owner_session:
        save_to_memory("user", user_message)
        save_to_memory("assistant", reply)

    return jsonify({
        "reply": reply,
        "owner": owner_detected
    })

@app.route("/upload", methods=["POST"])
def upload():
    global session_history

    file = request.files.get("file")
    message = request.form.get("message", "Analyze this file")

    if not file:
        return jsonify({"reply": "No file received."})

    filename = file.filename.lower()

    try:
        if filename.endswith(".docx"):
            doc = Document(file)
            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
            prompt = f"{message}\n\nDocument content:\n{text[:4000]}"
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                *session_history,
                {"role": "user", "content": prompt}
            ]
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages
            )
            reply = response.choices[0].message.content

        elif file.content_type.startswith("image/"):
            img_data = base64.b64encode(file.read()).decode("utf-8")
            media_type = file.content_type
            response = groq_client.chat.completions.create(
                model="llama-3.2-11b-vision-preview",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{media_type};base64,{img_data}"
                                }
                            },
                            {
                                "type": "text",
                                "text": message
                            }
                        ]
                    }
                ]
            )
            reply = response.choices[0].message.content
        else:
            reply = "Unsupported file type. Please upload an image or .docx file."

        session_history.append({"role": "user", "content": f"[File: {file.filename}] {message}"})
        session_history.append({"role": "assistant", "content": reply})

    except Exception as e:
        reply = f"Error processing file: {str(e)}"

    return jsonify({"reply": reply})

@app.route("/clear", methods=["POST"])
def clear():
    global session_history, is_owner_session
    session_history.clear()
    is_owner_session = False
    return jsonify({"status": "cleared"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
