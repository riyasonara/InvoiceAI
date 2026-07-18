import { useState, useEffect } from "react";
import "./App.css";

// Where our FastAPI backend lives. Later this becomes an env var (VITE_API_URL).
const API_URL = "http://localhost:8000";

function App() {
  const [file, setFile] = useState(null);
  const [invoice, setInvoice] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [invoices, setInvoices] = useState([]);

  // Fetch every saved invoice from the API. Reused on first load and
  // after each successful upload, so the list is always current.
  async function loadInvoices() {
    try {
      const response = await fetch(`${API_URL}/invoices`);
      const data = await response.json();
      setInvoices(data);
    } catch (err) {
      // A failed list shouldn't break the whole page; just log it.
      console.error("Failed to load invoices", err);
    }
  }

  // Run once, right after the page first renders (empty [] = "on mount").
  useEffect(() => {
    loadInvoices();
  }, []);

  async function handleUpload() {
    if (!file) return;

    // Reset UI state before starting a new request.
    setLoading(true);
    setError("");
    setInvoice(null);

    try {
      // Build the multipart/form-data body. "file" must match the
      // parameter name in our FastAPI endpoint: extract(file: UploadFile).
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_URL}/extract`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Server responded with ${response.status}`);
      }

      const data = await response.json();

      // Our API returns { success: false, error } when extraction failed.
      if (data.success === false) {
        setError(data.error);
      } else {
        setInvoice(data);
        loadInvoices(); // refresh the list to include the new/updated invoice
      }
    } catch (err) {
      setError("Could not reach the server. Is the API running on port 8000?");
    } finally {
      // Runs whether we succeeded or failed — always stop the spinner.
      setLoading(false);
    }
  }

  return (
    <div className="container">
      <header>
        <h1>InvoiceAI</h1>
        <p className="subtitle">
          Upload an invoice PDF and let AI extract the details.
        </p>
      </header>

      <div className="upload-card">
        <input
          type="file"
          accept="application/pdf"
          onChange={(e) => setFile(e.target.files[0])}
        />
        <button onClick={handleUpload} disabled={!file || loading}>
          {loading ? "Extracting…" : "Extract Invoice"}
        </button>
      </div>

      {error && <div className="error">{error}</div>}

      {invoice && (
        <div className="result-card">
          <h2>Extracted Invoice</h2>
          <table>
            <tbody>
              <tr><td>Vendor</td><td>{invoice.vendor ?? "—"}</td></tr>
              <tr><td>Invoice Number</td><td>{invoice.invoice_number ?? "—"}</td></tr>
              <tr><td>Invoice Date</td><td>{invoice.invoice_date ?? "—"}</td></tr>
              <tr><td>GST</td><td>{invoice.gst ?? "—"}</td></tr>
              <tr><td>Total</td><td>{invoice.total ?? "—"}</td></tr>
            </tbody>
          </table>
        </div>
      )}

      <div className="list-card">
        <h2>Saved Invoices ({invoices.length})</h2>
        {invoices.length === 0 ? (
          <p className="empty">No invoices yet. Upload one above.</p>
        ) : (
          <div className="table-scroll">
            <table className="list-table">
              <thead>
                <tr>
                  <th>Vendor</th>
                  <th>Number</th>
                  <th>Date</th>
                  <th>GST</th>
                  <th>Total</th>
                </tr>
              </thead>
              <tbody>
                {invoices.map((inv) => (
                  <tr key={inv.id}>
                    <td>{inv.vendor ?? "—"}</td>
                    <td>{inv.invoice_number ?? "—"}</td>
                    <td>{inv.invoice_date ?? "—"}</td>
                    <td>{inv.gst ?? "—"}</td>
                    <td>{inv.total ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
