import { useCallback, useEffect, useState } from "react";
import AirportDetail from "./components/AirportDetail";
import SearchBox from "./components/SearchBox";
import TestPanel from "./components/TestPanel";
import ThemeToggle from "./components/ThemeToggle";
import "./index.css";

const STATS_ENDPOINT = "http://localhost:8000/stats";

function formatStat(value) {
  return typeof value === "number" ? value.toLocaleString() : "—";
}

function StatBadge({ icon, value, label, isLoading }) {
  return (
    <span className="stat-badge" aria-busy={isLoading}>
      <span aria-hidden="true">{icon}</span>
      {isLoading ? (
        <span className="stat-skeleton" />
      ) : (
        <span className="stat-content stat-content-loaded">
          {value} {label}
        </span>
      )}
    </span>
  );
}

export default function App() {
  const [query, setQuery] = useState("");
  const [activeSearch, setActiveSearch] = useState("");
  const [selectedAirport, setSelectedAirport] = useState(null);
  const [stats, setStats] = useState(null);
  const [statsStatus, setStatsStatus] = useState("loading");

  useEffect(() => {
    let isActive = true;

    async function fetchStats() {
      try {
        const response = await fetch(STATS_ENDPOINT);

        if (!response.ok) {
          throw new Error(`Stats request failed with ${response.status}`);
        }

        const payload = await response.json();

        if (isActive) {
          setStats(payload);
          setStatsStatus("ready");
        }
      } catch {
        if (isActive) {
          setStats(null);
          setStatsStatus("error");
        }
      }
    }

    fetchStats();

    return () => {
      isActive = false;
    };
  }, []);

  const handleQueryChange = useCallback((nextQuery) => {
    setQuery(nextQuery);
    setActiveSearch(nextQuery);
  }, []);

  const handleTestSelect = useCallback((term) => {
    setQuery(term);
    setActiveSearch(term);
  }, []);

  const isStatsLoading = statsStatus === "loading";

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
          <StatBadge
            icon="✈"
            value={formatStat(stats?.total_airports)}
            label="Airports"
            isLoading={isStatsLoading}
          />
          <StatBadge
            icon="🌍"
            value={formatStat(stats?.total_countries)}
            label="Countries"
            isLoading={isStatsLoading}
          />
          <StatBadge icon="⚡" value="<50ms" label="Search" isLoading={false} />
          <StatBadge
            icon="🏙"
            value={formatStat(stats?.multi_airport_cities)}
            label="City Groups"
            isLoading={isStatsLoading}
          />
          <StatBadge
            icon="🏛"
            value={formatStat(stats?.capital_airports)}
            label="Capital Cities"
            isLoading={isStatsLoading}
          />
          <StatBadge
            icon="🔤"
            value={formatStat(stats?.airports_with_aliases)}
            label="With Aliases"
            isLoading={isStatsLoading}
          />
        </div>
      </section>

      <section className="search-section" aria-label="Airport search">
        <SearchBox
          value={query}
          onQueryChange={handleQueryChange}
          onResultSelect={setSelectedAirport}
        />
      </section>

      <TestPanel activeSearch={activeSearch} onSelect={handleTestSelect} />

      <footer className="footer">
        <span>© 2026 Fly Fairly. Built for the future of travel.</span>
        <span>FastAPI + Typesense + React</span>
      </footer>

      <AirportDetail
        airport={selectedAirport}
        onClose={() => setSelectedAirport(null)}
      />
    </main>
  );
}
