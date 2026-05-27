import { useState } from "react";

const MATCH_LABELS = {
  iata_exact: "Exact",
  city_exact: "City",
  region_match: "Region",
  fuzzy_match: "Fuzzy",
  city_group_match: "Group",
};

const TYPE_ICONS = {
  large_airport: "✈",
  medium_airport: "🛫",
  small_airport: "🛩",
};

const TYPE_LABELS = {
  large_airport: "Large",
  medium_airport: "Medium",
  small_airport: "Small",
};

function flagEmoji(countryCode) {
  if (!countryCode || countryCode.length !== 2) {
    return "";
  }

  return countryCode
    .toUpperCase()
    .replace(/./g, (letter) => String.fromCodePoint(127397 + letter.charCodeAt(0)));
}

function formatPopulation(value) {
  const population = Number(value);

  if (!Number.isFinite(population) || population <= 0) {
    return null;
  }

  if (population >= 1_000_000) {
    return `${(population / 1_000_000).toFixed(1).replace(".0", "")}M`;
  }

  if (population >= 1_000) {
    return `${Math.round(population / 1_000)}K`;
  }

  return population.toLocaleString();
}

export default function ResultCard({ result, highlighted, onMouseEnter, onOpenDetail }) {
  const [expanded, setExpanded] = useState(false);
  const matchTypes = result.match_types ?? [];
  const subAirports = result.sub_airports ?? [];
  const isMultiAirportCity = Boolean(result.is_multi_airport_city);
  const typeIcon = TYPE_ICONS[result.type] ?? "✈";
  const typeLabel = TYPE_LABELS[result.type] ?? "Airport";
  const flag = flagEmoji(result.country_code);
  const populationLabel = formatPopulation(result.city_population);

  function handleExpand(event) {
    event.stopPropagation();
    setExpanded((current) => !current);
  }

  return (
    <article
      className={`result-card ${highlighted ? "result-card-active" : ""}`}
      onMouseEnter={onMouseEnter}
      onClick={onOpenDetail}
      role="option"
      aria-selected={highlighted}
      tabIndex={-1}
    >
      <div className="result-card-main">
        <div className="result-left">
          <span className="iata-code">{result.iata}</span>
          <span className="type-icon" aria-label={typeLabel}>{typeIcon}</span>
        </div>

        <div className="result-center">
          <div className="result-heading">
            <h3>{result.name}</h3>
            {isMultiAirportCity && (
              <button className="airport-count" type="button" onClick={handleExpand}>
                {subAirports.length} airports
              </button>
            )}
          </div>

          <p className="result-location">
            <span>{result.city}</span>
            {flag && <span>{flag}</span>}
            {result.country && <span>{result.country}</span>}
          </p>

          {(result.is_capital || populationLabel) && (
            <div className="result-meta-tags">
              {result.is_capital && <span>🏛 Capital City</span>}
              {populationLabel && <span>👥 {populationLabel} pop</span>}
            </div>
          )}

          <div className="result-tags">
            {result.region && <span className="region-pill">{result.region}</span>}
            {matchTypes.map((type) => (
              <span key={type} className={`match-pill match-${type}`}>
                {MATCH_LABELS[type] ?? type}
              </span>
            ))}
          </div>
        </div>

        <div className="result-right">
          <span className="priority-ring" aria-label={`Priority ${result.priority}`}>
            {result.priority ?? 0}
          </span>
          <span className="arrow" aria-hidden="true">→</span>
        </div>
      </div>

      {isMultiAirportCity && expanded && subAirports.length > 0 && (
        <div className="sub-airport-list" onClick={(event) => event.stopPropagation()}>
          {subAirports.map((airport) => (
            <button key={airport.iata} className="sub-airport-card" type="button">
              <span className="sub-iata">{airport.iata}</span>
              <span>{airport.name}</span>
            </button>
          ))}
        </div>
      )}
    </article>
  );
}
