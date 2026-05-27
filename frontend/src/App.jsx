import { useCallback, useState } from "react";
import AirportDetail from "./components/AirportDetail";
import SearchBox from "./components/SearchBox";
import TestPanel from "./components/TestPanel";
import ThemeToggle from "./components/ThemeToggle";
import "./index.css";

export default function App() {
  const [query, setQuery] = useState("");
  const [activeSearch, setActiveSearch] = useState("");
  const [selectedAirport, setSelectedAirport] = useState(null);
  const [latestRateLimit, setLatestRateLimit] = useState(null);

  const handleQueryChange = useCallback((nextQuery) => {
    setQuery(nextQuery);
    setActiveSearch(nextQuery);
  }, []);

  const handleTestSelect = useCallback((term) => {
    setQuery(term);
    setActiveSearch(term);
  }, []);

  const handleResponse = useCallback((payload) => {
    setLatestRateLimit(payload?.rate_limit ?? null);
  }, []);

  return (
    <main className="app-shell">
      <header className="site-header">
        <a className="brand-lockup" href="/" aria-label="Fly Fairly home">
          <span className="brand-icon" aria-hidden="true">✈</span>
          <span className="brand-text">
            <strong>FLY FAIRLY</strong>
            <span>Airport Intelligence Engine</span>
          </span>
        </a>

        <div className="header-actions">
          <div className="live-status" aria-label="Typesense online">
            <span className="status-dot" aria-hidden="true" />
            <span>Typesense online</span>
          </div>
          <ThemeToggle />
        </div>
      </header>

      <section className="hero-section" aria-labelledby="hero-title">
        <div className="hero-orbit" aria-hidden="true" />
        <p className="hero-kicker">Global airport search</p>
        <h1 id="hero-title">
          <span>Find Any Airport.</span>
          <span className="gradient-text">Instantly.</span>
        </h1>
        <p className="hero-subtitle">
          8,000+ airports. Typos welcome.
          <br />
          Any language. Any script.
        </p>

        <div className="stat-row" aria-label="Search platform statistics">
          <span className="stat-badge">✈ 8,805 Airports</span>
          <span className="stat-badge">🌍 249 Countries</span>
          <span className="stat-badge">⚡ &lt;50ms Search</span>
        </div>
      </section>

      <section className="search-section" aria-label="Airport search">
        <SearchBox
          value={query}
          onQueryChange={handleQueryChange}
          onResultSelect={setSelectedAirport}
          onResponse={handleResponse}
        />
      </section>

      <TestPanel activeSearch={activeSearch} onSelect={handleTestSelect} />

      <footer className="footer">
        <span>© 2026 Fly Fairly. Built for the future of travel.</span>
        <span>FastAPI + Typesense + React</span>
      </footer>

      <AirportDetail
        airport={selectedAirport}
        rateLimit={latestRateLimit}
        onClose={() => setSelectedAirport(null)}
      />
    </main>
  );
}
