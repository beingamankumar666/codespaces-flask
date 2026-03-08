import os
import logging
import time
from flask import Flask, request, jsonify, render_template
import requests
import google.generativeai as genai
from datetime import datetime, timedelta

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)

# ============================================================================
# CONFIGURATION - Validate credentials at startup
# ============================================================================

try:
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    
    WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
    if not WHATSAPP_TOKEN:
        raise ValueError("WHATSAPP_TOKEN environment variable is required")
    
    PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
    if not PHONE_NUMBER_ID:
        raise ValueError("PHONE_NUMBER_ID environment variable is required")
    
    WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
    if not WHATSAPP_VERIFY_TOKEN:
        raise ValueError("WHATSAPP_VERIFY_TOKEN environment variable is required")
    
    # Provider priority order: list of available providers
    # Order: Best free tier → Fallback options
    AVAILABLE_PROVIDERS = []
    if GROQ_API_KEY:
        AVAILABLE_PROVIDERS.append("groq")  # PRIMARY: Fast, generous free tier
    if OPENROUTER_API_KEY:
        AVAILABLE_PROVIDERS.append("openrouter")  # FALLBACK: Multiple free models
    if GEMINI_API_KEY:
        AVAILABLE_PROVIDERS.append("gemini")  # BACKUP: Once quota resets
    
    if not AVAILABLE_PROVIDERS:
        raise ValueError("At least one AI provider key required: OPENROUTER_API_KEY, GROQ_API_KEY, or GEMINI_API_KEY")
    
    print("✅ All credentials validated successfully!")
    print(f"📍 Provider Priority: Groq → OpenRouter → Gemini")
except ValueError as e:
    print(f"❌ Configuration error: {e}")
    exit(1)

# ============================================================================
# CONFIGURATION - Credentials functions
# ============================================================================

def get_gemini_api_key():
    """Get validated Gemini API key."""
    return GEMINI_API_KEY

def get_groq_api_key():
    """Get validated Groq API key."""
    return GROQ_API_KEY

def get_openrouter_api_key():
    """Get validated OpenRouter API key."""
    return OPENROUTER_API_KEY

def get_whatsapp_token():
    """Get validated WhatsApp token."""
    return WHATSAPP_TOKEN

def get_phone_number_id():
    """Get validated phone number ID."""
    return PHONE_NUMBER_ID

def get_verify_token():
    """Get validated verification token."""
    return WHATSAPP_VERIFY_TOKEN

# ============================================================================
# RATE LIMITING & QUOTA MANAGEMENT
# ============================================================================

class ProviderQuota:
    """Track quota usage for each provider"""
    def __init__(self):
        self.provider_status = {
            "openrouter": {"disabled": False, "reset_time": None},
            "groq": {"disabled": False, "reset_time": None},
            "gemini": {"disabled": False, "reset_time": None}
        }
    
    def mark_provider_failed(self, provider, duration_hours=24):
        """Mark provider as failed temporarily"""
        self.provider_status[provider]["disabled"] = True
        self.provider_status[provider]["reset_time"] = datetime.now() + timedelta(hours=duration_hours)
        app.logger.warning(f"🔴 {provider.upper()} disabled for {duration_hours}h")
    
    def is_provider_available(self, provider):
        """Check if provider is available"""
        status = self.provider_status.get(provider, {})
        if not status.get("disabled"):
            return True
        
        reset_time = status.get("reset_time")
        if reset_time and datetime.now() > reset_time:
            status["disabled"] = False
            app.logger.info(f"🟢 {provider.upper()} quota reset!")
            return True
        return False
    
    def get_available_providers(self):
        """Get list of available providers in order"""
        available = []
        for provider in AVAILABLE_PROVIDERS:
            if self.is_provider_available(provider):
                available.append(provider)
        return available

quota_manager = ProviderQuota()

# ============================================================================
# AI PROVIDER IMPLEMENTATIONS
# ============================================================================

# Lazy-loaded Gemini client
_gemini_client = None
GEMINI_MODEL = 'gemini-2.0-flash'

def get_gemini_client():
    """Get or create Gemini model with lazy initialization."""
    global _gemini_client
    if _gemini_client is None and GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        _gemini_client = genai.GenerativeModel(GEMINI_MODEL)
    return _gemini_client

def call_openrouter(prompt):
    """Call OpenRouter API with multiple free model fallbacks"""
    try:
        if not OPENROUTER_API_KEY:
            return None, "OpenRouter API key not configured"
        
        if not quota_manager.is_provider_available("openrouter"):
            return None, "OpenRouter quota exceeded"
        
        # Free tier models on OpenRouter (try in order)
        models = [
            "mistralai/mistral-7b-instruct:free",
            "meta-llama/llama-2-70b-chat:free",
            "gryphe/mythomist-7b:free"
        ]
        
        url = "https://openrouter.io/api/v1/chat/completions"
        
        for model in models:
            try:
                headers = {
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 500
                }
                
                response = requests.post(url, headers=headers, json=payload, timeout=30)
                
                if response.status_code == 429:
                    app.logger.warning(f"OpenRouter rate limited for {model}")
                    continue
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("choices") and len(data["choices"]) > 0:
                        result = data["choices"][0]["message"]["content"].strip()
                        app.logger.info(f"✅ OpenRouter ({model}): Success")
                        return result, None
            except Exception as e:
                app.logger.warning(f"OpenRouter model {model} failed: {e}")
                continue
        
        return None, "All OpenRouter models failed"
        
    except Exception as e:
        app.logger.error(f"OpenRouter error: {e}")
        quota_manager.mark_provider_failed("openrouter", duration_hours=1)
        return None, str(e)

def call_gemini(prompt):
    """Call Gemini API with error handling"""
    try:
        if not GEMINI_API_KEY:
            return None, "Gemini API key not configured"
        
        if not quota_manager.is_provider_available("gemini"):
            return None, "Gemini quota exceeded"
        
        model = get_gemini_client()
        response = model.generate_content(prompt, timeout=30)
        
        if response and response.text:
            return response.text.strip(), None
        return None, "Empty response from Gemini"
        
    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "quota" in error_msg.lower():
            quota_manager.mark_provider_failed("gemini", duration_hours=24)
        app.logger.error(f"Gemini error: {error_msg}")
        return None, error_msg

def call_groq(prompt):
    """Call Groq API with error handling"""
    try:
        if not GROQ_API_KEY:
            return None, "Groq API key not configured"
        
        if not quota_manager.is_provider_available("groq"):
            return None, "Groq rate limited"
        
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "mixtral-8x7b-32768",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7,
            "max_tokens": 500
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 429:
            quota_manager.mark_provider_failed("groq", duration_hours=1)
            return None, "Groq rate limited"
        
        if response.status_code != 200:
            return None, f"Groq API error: {response.status_code}"
        
        data = response.json()
        if data.get("choices") and len(data["choices"]) > 0:
            return data["choices"][0]["message"]["content"].strip(), None
        return None, "Empty response from Groq"
        
    except Exception as e:
        app.logger.error(f"Groq error: {e}")
        return None, str(e)

def get_ai_response(prompt):
    """Get AI response with intelligent provider fallback"""
    available_providers = quota_manager.get_available_providers()
    
    if not available_providers:
        app.logger.error("❌ No AI providers available!")
        return "Badiya bhai, par sab servers thak gaye hain. 5 min baad try karna!"
    
    app.logger.info(f"🔄 Trying providers: {available_providers}")
    
    # Try each available provider in order
    for provider in available_providers:
        response = None
        error = None
        
        try:
            if provider == "openrouter":
                response, error = call_openrouter(prompt)
            elif provider == "groq":
                response, error = call_groq(prompt)
            elif provider == "gemini":
                response, error = call_gemini(prompt)
            
            if response:
                app.logger.info(f"✅ Got response from {provider}")
                return response
            
            app.logger.warning(f"⚠️ {provider} failed: {error}")
        except Exception as e:
            app.logger.error(f"Error with {provider}: {e}")
    
    # If all providers fail
    app.logger.error(f"❌ All providers failed: {available_providers}")
    return "Badiya bhai, par abhi server mein issue hai. Thodi der baad try karna!"

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
- Tools: GitHub Codespaces, Meta WhatsApp Business API, Groq & Gemini AI
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
    
    # ALWAYS return 200 OK immediately to Meta to prevent retry loop
    # Process message asynchronously
    if data:
        try:
            entry = data.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})
            messages = value.get("messages", [])
            
            if messages:
                message = messages[0]
                phone = message.get("from")
                text = message.get("text", {}).get("body") or message.get("button", {}).get("text")
                
                if not text:
                    interactive = message.get("interactive", {})
                    if interactive.get("type") == "button_reply":
                        text = interactive.get("button_reply", {}).get("title")
                
                if phone and text:
                    # Process message in background (return 200 immediately)
                    process_whatsapp_message(phone, text)
                    app.logger.info(f"Message queued: {phone} → {text}")
        except Exception as e:
            app.logger.error(f"Error parsing webhook: {e}")
    
    # Return 200 OK immediately - this stops Meta's retry queue
    return "OK", 200

def process_whatsapp_message(phone, text):
    """Process WhatsApp message and send response"""
    try:
        full_prompt = f"{AMAN_KUMAR_SYSTEM_PROMPT}\n\nUser ka message: {text}"
        ai_response = get_ai_response(full_prompt)
        
        app.logger.info(f"AI response: {ai_response}")
        
        # Send response back via WhatsApp
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
            
            app.logger.info(f"Sending message to {phone}")
            r = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if r.status_code in (200, 201):
                app.logger.info(f"✅ Message sent successfully to {phone}")
            else:
                app.logger.error(f"❌ WhatsApp API error: {r.status_code} - {r.text}")
                
        except Exception as e:
            app.logger.error(f"Failed to send WhatsApp message: {e}")
    
    except Exception as e:
        app.logger.error(f"Error processing message: {e}")

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
