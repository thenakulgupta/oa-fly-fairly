import { useState } from "react";

const MATCH_LABELS = {
  iata_exact: "IATA",
  city_exact: "City",
  city_group_match: "Group",
  fuzzy_match: "Fuzzy",
  region_match: "Region",
};

const TYPE_LABELS = {
  large_airport: "Large",
  medium_airport: "Medium",
  small_airport: "Small",
  city_group: "Group",
};

function countryFlag(countryCode) {
  if (!countryCode || countryCode.length !== 2) {
    return "";
  }

  return countryCode
    .toUpperCase()
    .replace(/./g, (letter) => String.fromCodePoint(127397 + letter.charCodeAt(0)));
}

function airportTypeClass(type) {
  if (type?.includes("large")) return "type-large";
  if (type?.includes("medium")) return "type-medium";
  if (type?.includes("small")) return "type-small";
  return "type-neutral";
}

export default function ResultCard({ result, highlighted, onMouseEnter, onSelect }) {
  const [expanded, setExpanded] = useState(false);
  const isMultiAirportCity = Boolean(result.is_multi_airport_city);
  const subAirports = result.sub_airports ?? [];
  const matchTypes = result.match_types ?? [];
  const typeLabel = TYPE_LABELS[result.type] ?? result.type?.replaceAll("_", " ") ?? "Airport";
  const flag = countryFlag(result.country_code);

  function handleCardClick() {
    if (isMultiAirportCity) {
      setExpanded((current) => !current);
      return;
    }

    onSelect?.();
  }

  function handleExpandClick(event) {
    event.stopPropagation();
    setExpanded((current) => !current);
  }

  return (
    <article
      className={`result-card ${highlighted ? "result-card-highlighted" : ""}`}
      onMouseEnter={onMouseEnter}
      onClick={handleCardClick}
      role="option"
      aria-selected={highlighted}
      tabIndex={-1}
    >
      <div className="result-main">
        <span className="iata-badge">{result.iata}</span>

        <div className="result-content">
          <div className="result-title-row">
            <h3>{result.name}</h3>
          </div>

          <p className="result-meta">
            {result.city}
            {result.country && <span>, {result.country}</span>}
            {flag && <span className="flag" aria-hidden="true">{flag}</span>}
          </p>

          {matchTypes.length > 0 && (
            <div className="match-pills" aria-label="Match types">
              {matchTypes.map((matchType) => (
                <span key={matchType} className={`match-pill match-${matchType}`}>
                  {MATCH_LABELS[matchType] ?? matchType}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="result-side">
          <span className={`type-badge ${airportTypeClass(result.type)}`}>{typeLabel}</span>
          {isMultiAirportCity && (
            <button
              className={`expand-button ${expanded ? "expand-button-open" : ""}`}
              type="button"
              onClick={handleExpandClick}
              aria-label={expanded ? "Collapse sub airports" : "Expand sub airports"}
            >
              <span aria-hidden="true" />
            </button>
          )}
        </div>
      </div>

      {isMultiAirportCity && expanded && subAirports.length > 0 && (
        <div className="sub-airports">
          {subAirports.map((airport) => (
            <button
              key={airport.iata}
              className="sub-airport"
              type="button"
              onClick={(event) => {
                event.stopPropagation();
                onSelect?.(airport);
              }}
            >
              <span className="iata-badge iata-badge-small">{airport.iata}</span>
              <span>{airport.display_name || airport.name}</span>
            </button>
          ))}
        </div>
      )}
    </article>
  );
}
