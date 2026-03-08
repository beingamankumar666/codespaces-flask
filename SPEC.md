# WhatsApp AI Bot - Aman Kumar Identity

## Project Overview
- **Project Name**: WhatsApp AI Bot with Aman Kumar Persona
- **Core Functionality**: A WhatsApp Business Cloud API bot that uses Google Gemini AI to respond as "Aman Kumar" - a tech-savvy cloud & AI enthusiast
- **Target Users**: WhatsApp users who message the business number

## Configuration

### API Credentials
Set these environment variables before running the server:

- `GEMINI_API_KEY` – Your Gemini/Google Generative API key
- `WHATSAPP_TOKEN` – Meta WhatsApp Business Cloud API token
- `PHONE_NUMBER_ID` – The WhatsApp phone number ID from your Business account
- `WHATSAPP_VERIFY_TOKEN` – A verification token you choose for webhook validation
- `WHATSAPP_BUSINESS_ACCOUNT_ID` – Your WhatsApp Business Account ID

## Identity Configuration

### Aman Kumar Persona
```json
{
  "name": "Aman Kumar",
  "persona": "Tech-savvy, Cloud & AI enthusiast, practical learner.",
  "communication_style": {
    "language": "Hinglish (Hindi written in Roman script)",
    "tone": "Direct, helpful, brotherly, and focused on solutions.",
    "catchphrases": ["Badiya", "Samajh gaya", "Setup par dhyan dena hai"]
  },
  "knowledge_base": {
    "current_focus": "Cloud-based AI WhatsApp Integration",
    "tools": ["GitHub Codespaces", "Meta WhatsApp Business API", "Gemini AI"],
    "philosophy": "Pehle setup aur raw material ko prioritize karna, phir execution."
  },
  "system_prompt": "Tum Aman Kumar ke AI avatar ho. Jab koi WhatsApp par tumse baat kare, toh aise jawab do jaise Aman Kumar khud baat kar raha ho. Faltu ki baatein nahi, seedha kaam ki baat aur doston wala ravaiya. Agar koi tech sawal pooche, toh use step-by-step samjhao."
}
```

## Functionality Specification

### Core Features
1. **Webhook Verification**: WhatsApp webhook verification endpoint (GET)
2. **Message Receiving**: Parse incoming WhatsApp messages from webhook payload
3. **AI Response Generation**: Use Gemini Pro model with Aman Kumar persona
4. **Message Sending**: Send AI responses back via WhatsApp Cloud API

### API Endpoints
- `GET /` - Root endpoint (renders index.html)
- `GET /webhook` - WhatsApp verification (hub.challenge)
- `POST /webhook` - Receive incoming WhatsApp messages

### Message Flow
1. User sends WhatsApp message → Meta sends webhook to our server
2. Server parses phone number and message text
3. Server calls Gemini AI with Aman Kumar persona prompt
4. Server sends AI response back to user via WhatsApp API

## Technical Stack
- **Framework**: Flask 2.3.2
- **AI**: Google Gemini API (google-generativeai)
- **WhatsApp**: Meta WhatsApp Business Cloud API
- **Hosting**: GitHub Codespaces

## Acceptance Criteria
- [x] Webhook verification returns 200 with hub.challenge
- [x] Incoming text messages are parsed correctly
- [x] Gemini API generates response in Hinglish with Aman Kumar persona
- [x] Response is sent back to WhatsApp user
- [x] Error handling for API failures
- [x] Logging for debugging
