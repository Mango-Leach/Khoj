# KHOJ

**Knowledge Hub for Opportunity Journey** — a voice-first learning-to-earning guide for rural India.

*Speak your skill. Find your first income.*

Built for the Citi hackathon. A student speaks about a skill they care about, in Hindi, Marathi or English, and gets 5 to 10 career paths that end in income. A verified mentor guides each step, reviews the student's practical work, and is paid as milestones are approved. On completion the student sees their top 3 opportunities, with scheme eligibility checked by a cited rules engine, never by the AI.

## What it does

- Voice intake in Hindi and Marathi, with confirm-back and typed fallback
- 5 to 10 career paths as five-rung income ladders, each with sources
- Mentor matching, assignments and rubric-based review
- Photo-based practical-work review with fraud and safety gates (a person always signs off high-risk work)
- Simulated payout ledger, top 3 opportunities, and an organisation dashboard (aggregates only)

## Stack

React + Vite + TypeScript (PWA) · FastAPI · MongoDB Atlas · Bhashini (speech and translation) · Ollama and Gemini (LLMs)

## Run it

Copy `.env.example` to `.env` and fill in what you have. Everything starts without any of it; the status panel shows what is missing.

```
# backend (Windows Git Bash; on macOS/Linux use: source .venv/bin/activate)
cd backend
python -m venv .venv && . .venv/Scripts/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# frontend (second terminal)
cd frontend
npm install
npm run dev
```

Open `https://localhost:5173`. On a phone on the same Wi-Fi, open the `Network` address Vite prints and accept the certificate warning once. Phones need HTTPS for the microphone, camera and service worker. Allow inbound port 5173 in the firewall if the phone cannot connect.

Tests: `cd backend && python -m pytest` and `cd frontend && npm test`.


