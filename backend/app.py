import io
import os
import threading
import time
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv  # type: ignore
from flask import Flask, jsonify, request, send_file  # type: ignore
from flask_cors import CORS  # type: ignore
from supabase import create_client  # type: ignore
from twilio.rest import Client as TwilioClient  # type: ignore
import qrcode  # type: ignore
import serial  # type: ignore

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
WEB_URL = os.getenv("WEB_URL", "http://localhost:5000")
SERIAL_PORT = os.getenv("SERIAL_PORT")
SERIAL_BAUDRATE = int(os.getenv("SERIAL_BAUDRATE", "115200"))
TICKET_EXPIRATION_SECONDS = int(os.getenv("TICKET_EXPIRATION_SECONDS", "600"))

app = Flask(__name__)
CORS(app)

INVALID_ENV_PATTERNS = ["your-", "your_", "example", "xxxx", "your supabase"]

def is_valid_env_value(value: str | None) -> bool:
    if not value:
        return False
    value = value.strip().lower()
    # Check for placeholder patterns but allow real Supabase/Twilio URLs
    if any(pattern in value for pattern in INVALID_ENV_PATTERNS):
        return False
    # Ensure it's not just a generic example
    if value.startswith("ac") and len(value) == 34 and value.count("x") > 10:
        return False  # Account SID that's all X's
    return True

use_supabase = is_valid_env_value(SUPABASE_URL) and is_valid_env_value(SUPABASE_KEY)
use_twilio = (
    is_valid_env_value(TWILIO_ACCOUNT_SID)
    and is_valid_env_value(TWILIO_AUTH_TOKEN)
    and is_valid_env_value(TWILIO_FROM_NUMBER)
)

supabase = None
if use_supabase:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        app.logger.info("Supabase client initialized successfully.")
    except Exception as e:
        app.logger.warning(f"Failed to initialize Supabase: {e}. Falling back to in-memory ticket store.")
        use_supabase = False
else:
    app.logger.warning(
        "SUPABASE_URL or SUPABASE_KEY not set or placeholder values detected; using in-memory ticket store."
    )

twilio_client = None
if use_twilio:
    try:
        twilio_client = TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        app.logger.info("Twilio client initialized successfully.")
    except Exception as e:
        app.logger.warning(f"Failed to initialize Twilio: {e}. SMS sending will be skipped.")
        use_twilio = False
else:
    app.logger.warning("Twilio settings not set or placeholder values detected; SMS sending will be skipped.")

ticket_store = {}

serial_lock = threading.Lock()
serial_connection = None
current_ticket = None


def utcnow_iso():
    return datetime.now(timezone.utc).isoformat()


def send_twilio_sms(phone_number: str, ticket_id: str) -> str:
    if not use_twilio or twilio_client is None:
        app.logger.info("Skipping Twilio SMS for ticket %s because Twilio is not configured.", ticket_id)
        return "SMS is not configured."

    message = (
        f"Smart Parking QR ticket created."
        f"\nTicket ID: {ticket_id}"
        f"\nOpen this link on your phone to view your QR: {WEB_URL}/api/qr/{ticket_id}"
    )

    try:
        twilio_client.messages.create(
            body=message,
            from_=TWILIO_FROM_NUMBER,
            to=phone_number,
        )
        app.logger.info("Twilio SMS sent for ticket %s to %s", ticket_id, phone_number)
        return "SMS sent successfully."
    except Exception as exc:
        app.logger.exception("Failed to send Twilio SMS for ticket %s", ticket_id)
        return f"SMS failed: {exc}"


def generate_qr_image_bytes(code: str) -> io.BytesIO:
    qr = qrcode.QRCode(border=2, version=1)
    qr.add_data(code)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    buffer.seek(0)
    return buffer


def store_ticket(ticket_id: str, code: str, phone: str) -> None:
    expires_at = datetime.now(timezone.utc).timestamp() + TICKET_EXPIRATION_SECONDS
    payload = {
        "id": ticket_id,
        "qr_code": code,
        "phone": phone,
        "status": "issued",
        "created_at": utcnow_iso(),
        "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
    }
    if use_supabase and supabase:
        try:
            supabase.table("tickets").insert(payload).execute()
        except Exception as e:
            app.logger.error(f"Failed to store ticket in Supabase: {e}. Using in-memory store.")
            ticket_store[ticket_id] = payload
    else:
        ticket_store[ticket_id] = payload


def fetch_ticket_by_id(ticket_id: str):
    if use_supabase and supabase:
        try:
            response = supabase.table("tickets").select("*").eq("id", ticket_id).single().execute()
            return response.data if response.data else None
        except Exception as e:
            app.logger.warning(f"Failed to fetch ticket from Supabase: {e}. Falling back to in-memory store.")
    return ticket_store.get(ticket_id)


def fetch_ticket_by_code(code: str):
    if use_supabase and supabase:
        try:
            response = supabase.table("tickets").select("*").eq("qr_code", code).single().execute()
            return response.data if response.data else None
        except Exception as e:
            app.logger.warning(f"Failed to fetch ticket from Supabase: {e}. Falling back to in-memory store.")
    return next((ticket for ticket in ticket_store.values() if ticket["qr_code"] == code), None)


def fetch_all_tickets():
    if use_supabase and supabase:
        try:
            response = supabase.table("tickets").select("*").order("created_at", desc=True).execute()
            return response.data if response.data else []
        except Exception as e:
            app.logger.warning(f"Failed to fetch tickets from Supabase: {e}. Falling back to in-memory store.")
    return sorted(ticket_store.values(), key=lambda ticket: ticket.get("created_at", ""), reverse=True)


def update_ticket_status(ticket_id: str, status: str):
    if use_supabase and supabase:
        supabase.table("tickets").update({"status": status}).eq("id", ticket_id).execute()
    elif ticket_id in ticket_store:
        ticket_store[ticket_id]["status"] = status


def is_ticket_valid(ticket: dict) -> bool:
    if not ticket or ticket.get("status") != "issued":
        return False
    expires_at = ticket.get("expires_at")
    if not expires_at:
        return False
    expire_time = datetime.fromisoformat(expires_at)
    return datetime.now(timezone.utc) <= expire_time


def create_ticket(phone: str) -> dict:
    global current_ticket
    ticket_id = uuid.uuid4().hex
    code = uuid.uuid4().hex
    store_ticket(ticket_id, code, phone)
    sms_status = send_twilio_sms(phone, ticket_id)
    current_ticket = {
        "id": ticket_id,
        "qr_code": code,
        "phone": phone,
        "created_at": utcnow_iso(),
        "sms_status": sms_status,
    }
    send_serial_line(f"TICKET_SENT|{ticket_id}|{code}")
    return current_ticket


def validate_scan(code: str) -> dict:
    ticket = fetch_ticket_by_code(code)
    if ticket and is_ticket_valid(ticket):
        update_ticket_status(ticket["id"], "validated")
        return ticket
    return None


def send_serial_line(text: str) -> None:
    global serial_connection
    with serial_lock:
        if serial_connection and serial_connection.is_open:
            serial_connection.write((text + "\n").encode("utf-8"))
            serial_connection.flush()


def process_serial_line(line: str) -> None:
    if line.startswith("REQUEST_TICKET|"):
        _, phone = line.split("|", 1)
        app.logger.info("FPGA requested ticket for %s", phone)
        create_ticket(phone)
        return

    if line.startswith("SCAN|"):
        _, code = line.split("|", 1)
        app.logger.info("FPGA scanned code %s", code)
        ticket = validate_scan(code)
        if ticket:
            send_serial_line(f"VALID|{ticket['id']}")
        else:
            send_serial_line("INVALID")
        return

    app.logger.info("Unknown serial command: %s", line)


def serial_listener():
    global serial_connection
    if not SERIAL_PORT:
        app.logger.info("SERIAL_PORT is not configured; serial listener disabled.")
        return

    if not os.path.exists(SERIAL_PORT):
        app.logger.warning("Configured serial port %s does not exist; serial listener disabled.", SERIAL_PORT)
        return

    while True:
        try:
            if serial_connection is None or not serial_connection.is_open:
                serial_connection = serial.Serial(SERIAL_PORT, SERIAL_BAUDRATE, timeout=1)
                app.logger.info("Opened serial port %s %d", SERIAL_PORT, SERIAL_BAUDRATE)

            raw_line = serial_connection.readline()
            if not raw_line:
                continue
            line = raw_line.decode("utf-8", errors="ignore").strip()
            if line:
                process_serial_line(line)
        except serial.SerialException as exc:
            app.logger.warning("Serial exception: %s", exc)
            time.sleep(5)
        except Exception as exc:
            app.logger.exception("Error reading serial: %s", exc)
            time.sleep(1)


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/latest-ticket")
def latest_ticket_route():
    if not current_ticket:
        return jsonify({})
    ticket = current_ticket.copy()
    ticket["qr_url"] = request.url_root.rstrip("/") + f"/api/qr/{ticket['id']}"
    ticket["sms_enabled"] = use_twilio
    return jsonify(ticket)


@app.route("/api/qr/<ticket_id>")
def qr_image(ticket_id: str):
    ticket = fetch_ticket_by_id(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket not found"}), 404
    buffer = generate_qr_image_bytes(ticket["qr_code"])
    return send_file(buffer, mimetype="image/png")


@app.route("/api/tickets")
def tickets_route():
    tickets = fetch_all_tickets()
    return jsonify(tickets)


@app.route("/api/generate-ticket", methods=["POST"])
def generate_ticket():
    data = request.get_json(force=True)
    phone = data.get("phone")
    if not phone:
        return jsonify({"error": "Missing phone"}), 400
    ticket = create_ticket(phone)
    ticket["qr_url"] = request.url_root.rstrip("/") + f"/api/qr/{ticket['id']}"
    ticket["sms_enabled"] = use_twilio
    ticket["sms_status"] = ticket.get("sms_status", "SMS status unavailable")
    return jsonify(ticket)


@app.route("/api/validate", methods=["POST"])
def validate_route():
    data = request.get_json(force=True)
    code = data.get("code")
    if not code:
        return jsonify({"error": "Missing code"}), 400
    ticket = validate_scan(code)
    if ticket:
        return jsonify({"valid": True, "ticket": ticket})
    return jsonify({"valid": False}), 404


def start_serial_thread():
    thread = threading.Thread(target=serial_listener, daemon=True)
    thread.start()


if __name__ == "__main__":
    start_serial_thread()
    app.run(host="0.0.0.0", port=5000, debug=True)
