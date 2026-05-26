import { useEffect, useState } from 'react';
import { apiBaseUrl, fetchLatestTicket, fetchTickets, generateTicket } from './api';

function App() {
  const [phone, setPhone] = useState('');
  const [ticket, setTicket] = useState(null);
  const [tickets, setTickets] = useState([]);
  const [status, setStatus] = useState('');
  const [error, setError] = useState(null);

  useEffect(() => {
    loadLatest();
    loadTickets();
  }, []);

  async function loadLatest() {
    setError(null);
    const response = await fetchLatestTicket();
    if (response) {
      setTicket(response);
    }
  }

  async function loadTickets() {
    const response = await fetchTickets();
    setTickets(response || []);
  }

  async function handleGenerate(e) {
    e.preventDefault();
    setError(null);
    setStatus('Sending request...');
    try {
      const newTicket = await generateTicket(phone);
      setTicket(newTicket);
      setStatus(
        newTicket.sms_enabled
          ? 'Ticket created and SMS requested.'
          : 'Ticket created. SMS is not configured; the QR code is shown below.'
      );
      await loadTickets();
    } catch (err) {
      setError(err.message || 'Unable to create ticket');
      setStatus('');
    }
  }

  return (
    <div className="app-shell">
      <header>
        <h1>Smart Parking</h1>
        <p>Generate a QR ticket and verify scans from FPGA via USB.</p>
      </header>

      <section className="card">
        <h2>Generate Ticket</h2>
        <form onSubmit={handleGenerate}>
          <label>
            Phone number
            <input
              type="tel"
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
              placeholder="+1234567890"
              required
            />
          </label>
          <button type="submit">Create ticket</button>
        </form>
        {status && <p className="notice">{status}</p>}
        {error && <p className="error">{error}</p>}
      </section>

      <section className="card">
        <h2>Latest Ticket</h2>
        {ticket ? (
          <div className="ticket-preview">
            <p>
              <strong>ID:</strong> {ticket.id}
            </p>
            <p>
              <strong>Phone:</strong> {ticket.phone}
            </p>
            <img
              src={`${apiBaseUrl}/api/qr/${ticket.id}`}
              alt="Ticket QR code"
              className="qr-image"
            />
            {ticket.sms_status && (
              <p className="notice">{ticket.sms_status}</p>
            )}
            {ticket.qr_url && (
              <p className="help-text">
                QR link: <a href={ticket.qr_url} target="_blank" rel="noreferrer">Open QR image</a>
              </p>
            )}
            <p className="help-text">
              The FPGA can validate this ticket when it scans the QR code.
            </p>
          </div>
        ) : (
          <p>No ticket generated yet.</p>
        )}
      </section>

      <section className="card">
        <h2>Admin Dashboard</h2>
        <p className="help-text">All tickets generated so far, including status and expiry details.</p>
        {tickets.length > 0 ? (
          <div className="admin-table-wrapper">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Phone</th>
                  <th>Status</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {tickets.map((item) => (
                  <tr key={item.id}>
                    <td>{item.id}</td>
                    <td>{item.phone}</td>
                    <td>{item.status || 'issued'}</td>
                    <td>{new Date(item.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p>No tickets have been generated yet.</p>
        )}
      </section>
    </div>
  );
}

export default App;
