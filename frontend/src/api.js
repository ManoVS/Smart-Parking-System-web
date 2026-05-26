const explicitApiBaseUrl = import.meta.env.VITE_API_BASE_URL;
const isLocalhost = ['localhost', '127.0.0.1'].includes(window.location.hostname);
// On localhost use the local backend port. In production, default to the
// Vercel experimental backend routePrefix `/_/backend` so frontend can
// call the backend deployed as a Vercel service at `https://<project>/_/backend`.
export const apiBaseUrl = explicitApiBaseUrl
  ? explicitApiBaseUrl
  : isLocalhost
  ? `${window.location.protocol}//${window.location.hostname}:5000`
  : `${window.location.origin}/_/backend`;

export async function fetchLatestTicket() {
  const response = await fetch(`${apiBaseUrl}/api/latest-ticket`);
  if (!response.ok) {
    return null;
  }
  return response.json();
}

export async function fetchTickets() {
  const response = await fetch(`${apiBaseUrl}/api/tickets`);
  if (!response.ok) {
    return [];
  }
  return response.json();
}

export async function generateTicket(phone) {
  const response = await fetch(`${apiBaseUrl}/api/generate-ticket`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ phone }),
  });
  if (!response.ok) {
    const body = await response.json();
    throw new Error(body.error || 'Failed to generate ticket');
  }
  return response.json();
}
