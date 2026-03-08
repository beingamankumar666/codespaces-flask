# GitHub Codespaces ♥️ Flask

Welcome to your shiny new Codespace running Flask! We've got everything fired up and running for you to explore Flask.

You've got a blank canvas to work on from a git perspective as well. There's a single initial commit with the what you're seeing right now - where you go from here is up to you!

Everything you do here is contained within this one codespace. There is no repository on GitHub yet. If and when you’re ready you can click "Publish Branch" and we’ll create your repository and push up your project. If you were just exploring then and have no further need for this code then you can simply delete your codespace and it's gone forever.

## WhatsApp AI Bot

This project implements a simple Flask-based WhatsApp AI chatbot powered by Google's Gemini API. The bot responds with Aman Kumar's personality in Hinglish.

### Configuration

Set the following environment variables before running the server (or replace with actual values in a `.env` file):

- `GEMINI_API_KEY` – Your Gemini/Google Generative API key (placeholder: `YOUR_GEMINI_API_KEY`).
- `WHATSAPP_TOKEN` – Meta WhatsApp Business Cloud API token (placeholder: `YOUR_WHATSAPP_TOKEN`).
- `PHONE_NUMBER_ID` – The WhatsApp phone number ID from your Business account (placeholder: `YOUR_PHONE_NUMBER_ID`).
- `WHATSAPP_VERIFY_TOKEN` – A verification token you choose for webhook validation.

### Running

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the Flask app (replace `export` with `set` on Windows):

```bash
export GEMINI_API_KEY="..."
export WHATSAPP_TOKEN="..."
export PHONE_NUMBER_ID="..."
export WHATSAPP_VERIFY_TOKEN="..."
flask --debug run
```

The `/webhook` endpoint will handle WhatsApp verification and messages.

---

To run the original starter application:

```
flask --debug run
```
