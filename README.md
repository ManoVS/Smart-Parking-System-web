# Smart Parking QR Website

This repository contains a Python Flask backend and a React frontend for a smart parking system.

## Architecture

- `backend/` contains the Flask API, USB serial listener for FPGA communication, Twilio SMS sending, and Supabase ticket storage.
- `frontend/` contains the React app that allows manual ticket generation and shows the latest QR ticket.

## How it works

1. FPGA sends a USB serial message to the PC.
2. The Flask backend reads the serial input and creates a ticket if it receives `REQUEST_TICKET|+123...`.
3. The backend stores the ticket in Supabase, generates a QR code, and sends a Twilio SMS with a link to view the QR.
4. When the FPGA scans a QR code, it sends `SCAN|<code>` via USB.
5. The backend validates the code against Supabase and replies with `VALID|<ticket_id>` or `INVALID`.

## Setup

### 1. Backend

1. Copy `backend/.env.example` to `backend/.env` and fill in your Twilio and Supabase credentials.
2. Install Python dependencies:

```bash
cd /home/manoranjan-seker/SY_PRO/backend
python -m pip install -r requirements.txt
```

3. Create a Supabase table called `tickets` with this schema:

```sql
create table tickets (
  id text primary key,
  qr_code text unique,
  phone text,
  status text,
  created_at timestamptz,
  expires_at timestamptz
);
```

4. Start the backend:

```bash
python app.py
```

### 2. Frontend

1. Install frontend dependencies:

```bash
cd /home/manoranjan-seker/SY_PRO/frontend
npm install
```

2. Start the development server:

```bash
npm run dev
```

3. Open `http://localhost:5173` in your browser.

## FPGA serial protocol

- Request a new ticket:
  - `REQUEST_TICKET|+1234567890`
- Scan a QR code:
  - `SCAN|<qr_code>`
- Backend responses:
  - `TICKET_SENT|<ticket_id>|<code>`
  - `VALID|<ticket_id>`
  - `INVALID`

## Notes

- Update `SERIAL_PORT` in `backend/.env` for your FPGA USB device.
- If your browser frontend is served from a different host, set `VITE_API_BASE_URL` in `frontend/.env` or edit `frontend/src/api.js`.
