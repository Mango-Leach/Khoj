# KHOJ

**Knowledge Hub for Opportunity Journey** — a voice-first learning-to-earning guidance system for rural India.

*Not what you studied, what you already do.*

Built for the Citi hackathon. KHOJ starts from what a learner already does, maps it to skills and occupations, links it to their school curriculum, and builds a step-by-step ladder to a verified first income. A local teacher or facilitator stays in the loop.

## Features

- Picture quiz and voice onboarding in the student's language
- Curriculum-to-Livelihood Bridge
- Pathway ladders with cited scheme eligibility (Eligible / Not eligible / Check with the office)
- Teacher Copilot and Local Demand Pulse
- Khoj Passport: teacher-vouched QR credential that verifies offline
- Offline-first with sync, and shared-phone profiles

## Stack

React + Vite + TypeScript (PWA) · FastAPI + SQLite

## Run

```
# backend
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && python ../scripts/seed.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# frontend
cd frontend && npm install && npm run dev -- --host
```

*(Code is not scaffolded yet.)*
