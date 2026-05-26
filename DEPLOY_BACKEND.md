Backend deployment guide

This project ships a Flask backend in `backend/`. Below are three easy ways to host it.

Option A — Render (recommended)
1. Go to https://render.com and sign in.
2. Create a new "Web Service" and connect your GitHub repo `ManoVS/Smart-Parking-System-web`.
3. Choose branch `main` and select "Docker" as the environment.
4. Set the Dockerfile path to `backend/Dockerfile` (the repo contains one).
5. Add environment variables (SUPABASE_URL, SUPABASE_KEY, TWILIO_* etc.) in the Render UI.
6. Deploy. Render will build and run the container on port 5000.

Option B — Railway
1. Create a new project and import from GitHub.
2. Use the Dockerfile at `backend/Dockerfile` or set build/start commands:
   - Build: `pip install -r requirements.txt`
   - Start: `gunicorn app:app --bind 0.0.0.0:5000`
3. Add environment variables in Railway's settings.

Option C — Heroku (classic)
1. Install the Heroku CLI and log in.
2. From repo root run:

```bash
cd backend
heroku create your-app-name
git push heroku main
heroku config:set SUPABASE_URL=... SUPABASE_KEY=... TWILIO_ACCOUNT_SID=... TWILIO_AUTH_TOKEN=... TWILIO_FROM_NUMBER=...
```

Note: Heroku will use the `Procfile` included in `backend/` which runs `gunicorn app:app`.

Local testing

To run locally in Docker:

```bash
# from repo root
docker build -t smart-parking-backend -f backend/Dockerfile .
docker run -p 5000:5000 --env-file backend/.env -it smart-parking-backend
```

If you want, I can create a `render.yaml` (already added) and trigger a deploy for you, or generate platform-specific config for Railway or Heroku. Tell me which host to configure next.
