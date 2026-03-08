import os
import logging
import time
from flask import Flask, request, jsonify, render_template
import requests
import google.generativeai as genai

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# ============================================================================
# CONFIGURATION - Validate credentials at startup
# ============================================================================

# Validate all required environment variables at startup
try:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable is required")
    
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
    if not WHATSAPP_TOKEN:
        raise ValueError("WHATSAPP_TOKEN environment variable is required")
    
    PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
    if not PHONE_NUMBER_ID:
        raise ValueError("PHONE_NUMBER_ID environment variable is required")
    
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
    if not WHATSAPP_VERIFY_TOKEN:
        raise ValueError("WHATSAPP_VERIFY_TOKEN environment variable is required")
    
    print("✅ All credentials validated successfully!")
except ValueError as e:
    print(f"❌ Configuration error: {e}")
    print("Please set the required environment variables in your .env file")
    exit(1)

# ============================================================================
# CONFIGURATION - Credentials functions
# ============================================================================

def get_gemini_api_key():
    """Get validated Gemini API key."""
    return GEMINI_API_KEY

def get_whatsapp_token():
    """Get validated WhatsApp token."""
    return WHATSAPP_TOKEN

def get_phone_number_id():
    """Get validated phone number ID."""
    return PHONE_NUMBER_ID

def get_verify_token():
    """Get validated verification token."""
    return WHATSAPP_VERIFY_TOKEN

# Lazy-loaded Gemini client
_gemini_client = None

def get_gemini_client():
    """Get or create Gemini model with lazy initialization."""
    global _gemini_client
    if _gemini_client is None:
        genai.configure(api_key=get_gemini_api_key())
        _gemini_client = genai.GenerativeModel(GEMINI_MODEL)
    return _gemini_client

# ============================================================================
# AMAN KUMAR PERSONA - Detailed System Prompt
# ============================================================================

AMAN_KUMAR_SYSTEM_PROMPT = """Tum Aman Kumar ke AI avatar ho. Tumhara profile yeh hai:

**Name**: Aman Kumar
**Persona**: Tech-savvy, Cloud & AI enthusiast, practical learner

**Communication Style**:
- Language: Hinglish (Hindi written in Roman script)
- Tone: Direct, helpful, brotherly, and focused on solutions
- Catchphrases: "Badiya", "Samajh gaya", "Setup par dhyan dena hai"

**Knowledge Base**:
- Current Focus: Cloud-based AI WhatsApp Integration
- Tools: GitHub Codespaces, Meta WhatsApp Business API, Gemini AI
- Philosophy: "Pehle setup aur raw material ko prioritize karna, phir execution."

**Instructions**:
1. Jab koi WhatsApp par tumse baat kare, toh aise jawab do jaise Aman Kumar khud baat kar raha ho
2. Faltu ki baatein nahi, seedha kaam ki baat aur doston wala ravaiya
3. Agar koi tech sawal pooche, toh use step-by-step samjhao
4. Kabhi kabhi code bhi share kar sakte ho agar needed ho
5. Helpful rahe hamesha, lekin concise - lamba mat likho

Tumse baat karne wale koaise greet karna hai:
- "Namaste bhai/bahin! Aman Kumar bol raha hoon. Kya help chahiye?"

Ab niche user ka message hai. Aman Kumar jaise reply karo:"""

# Create Gemini model instance (we'll use it when calling API)
# The model name for the new API
GEMINI_MODEL = 'gemini-2.0-flash'

# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route("/")
def index():
    """Root endpoint to verify app is running."""
    return render_template("index.html", title="WhatsApp AI Bot - Aman Kumar")

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "bot": "Aman Kumar AI"})

# ============================================================================
# WHATSAPP WEBHOOK HANDLER
# ============================================================================

@app.route("/webhook", methods=["GET", "POST"])
def whatsapp_webhook():
    """Handle the WhatsApp Business Cloud webhook.
    
    GET requests are used for verification (hub.challenge), 
    POST for incoming messages.
    """
    # -------------------------------------------------------------------------
    # WEBHOOK VERIFICATION (GET)
    # -------------------------------------------------------------------------
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        
        app.logger.info(f"Webhook verification request: mode={mode}, token={token}")
        
        if mode == "subscribe" and token == get_verify_token():
            app.logger.info("Webhook verified successfully!")
            return challenge, 200
        else:
            app.logger.warning(f"Verification failed: mode={mode}, expected token={get_verify_token()}")
            return "Verification token mismatch", 403

    # -------------------------------------------------------------------------
    # INCOMING MESSAGES (POST)
    # -------------------------------------------------------------------------
    data = request.get_json(silent=True)
    app.logger.info(f"Received webhook payload: {data}")
    
    # TEMPORARY FIX: Return 200 OK immediately to stop Meta's retry loop
    # This breaks the queue of old retrying messages
    # Comment this out once Google quota is reset
    return "OK", 200
    
    if not data:
        return "No data", 400

    # Extract phone number and message text
    phone = None
    text = None
    
    try:
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        
        if not messages:
            return "No message", 200
            
        message = messages[0]
        phone = message.get("from")
        
        # Text messages are under text.body
        text = message.get("text", {}).get("body")
        
        # Fallback: button replies
        if not text:
            text = message.get("button", {}).get("text")
            
        # Fallback: interactive messages
        if not text:
            interactive = message.get("interactive", {})
            if interactive.get("type") == "button_reply":
                text = interactive.get("button_reply", {}).get("title")
                
    except Exception as e:
        app.logger.error(f"Failed to parse incoming webhook: {e}")
        return "Bad Request", 400

    if not phone or not text:
        app.logger.warning(f"Missing phone or text; phone={phone}, text={text}")
        return "Ignored", 200

    app.logger.info(f"Received message from {phone}: {text}")

    # -------------------------------------------------------------------------
    # GENERATE AI RESPONSE USING GEMINI
    # -------------------------------------------------------------------------
    ai_response = None
    
    try:
        # Build the prompt with system prompt and user message
        full_prompt = f"{AMAN_KUMAR_SYSTEM_PROMPT}\n\nUser ka message: {text}"
        
        # Generate response using Gemini
        model = get_gemini_client()
        response = model.generate_content(full_prompt)
        
        # Extract text from response
        if response and response.text:
            ai_response = response.text.strip()
        else:
            ai_response = "Badiya, lekin kuch response nahi mila. Doobara try karo!"
            
        app.logger.info(f"Gemini response: {ai_response}")
        
    except Exception as e:
        app.logger.error(f"Error calling Gemini API: {e}")
        ai_response = "Sorry bhai, kuch technical issue ho gaya hai. Thodi der baad try karo!"

    # -------------------------------------------------------------------------
    # SEND RESPONSE BACK VIA WHATSAPP BUSINESS API
    # -------------------------------------------------------------------------
    
    # Note: Removed blocking time.sleep(1.5) to avoid request handler delays
    # If rate limiting issues occur, consider implementing async queue or backoff
    
    try:
        url = f"https://graph.facebook.com/v18.0/{get_phone_number_id()}/messages"
        headers = {
            "Authorization": f"Bearer {get_whatsapp_token()}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": ai_response},
        }
        
        app.logger.info(f"Sending WhatsApp message to {phone}")
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if r.status_code not in (200, 201):
            app.logger.error(f"WhatsApp API error: {r.status_code} - {r.text}")
        else:
            app.logger.info("Message sent successfully!")
            
    except Exception as e:
        app.logger.error(f"Failed to send WhatsApp message: {e}")

    return "OK", 200


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    port = int(os.getenv("PORT", 5000))
    app.logger.info(f"Starting WhatsApp AI Bot on port {port}")
    app.logger.info("Gemini API configured successfully")
    app.logger.info(f"Phone Number ID: {get_phone_number_id()}")
    
    app.run(host="0.0.0.0", port=port, debug=True)
