import os
from flask import Flask, render_template, request, jsonify
from groq import Groq
import requests

app = Flask(__name__)
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
conversation_history = []

def chat_groq(messages):
    response = client.chat.completions.create(
       model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": """You are a personal AI assistant created by Phonex (72phonex), a CSE student at MAIT Rohini, Delhi. He built you using Python Flask and Groq API. You know everything about your creator Phonex and are loyal to him. When someone asks who made you, say Phonex created you. You are helpful, smart, and friendly."""},
            *messages
        ]
    )
    return response.choices[0].message.content

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/status")
def status():
    return jsonify({"mode": "online", "model": "Llama 70B (Groq)"})

@app.route("/chat", methods=["POST"])
def chat():
    user_message = request.json.get("message")
    conversation_history.append({
        "role": "user",
        "content": user_message
    })
    try:
        reply = chat_groq(conversation_history)
    except Exception as e:
        reply = f"Error: {str(e)}"
    conversation_history.append({
        "role": "assistant",
        "content": reply
    })
    return jsonify({"reply": reply})

@app.route("/clear", methods=["POST"])
def clear():
    conversation_history.clear()
    return jsonify({"status": "cleared"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
