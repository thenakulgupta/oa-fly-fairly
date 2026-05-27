const MATCH_LABELS = {
  iata_exact: "Exact IATA",
  city_exact: "City",
  region_match: "Region",
  fuzzy_match: "Fuzzy",
  city_group_match: "City group",
};

function flagEmoji(countryCode) {
  if (!countryCode || countryCode.length !== 2) {
    return "";
  }

  return countryCode
    .toUpperCase()
    .replace(/./g, (letter) => String.fromCodePoint(127397 + letter.charCodeAt(0)));
}

function typeLabel(type) {
  return type?.replaceAll("_", " ") || "Airport";
}

function formatPopulation(value) {
  const population = Number(value);

  if (!Number.isFinite(population) || population <= 0) {
    return "—";
  }

  if (population >= 1_000_000) {
    return `${(population / 1_000_000).toFixed(1).replace(".0", "")}M`;
  }

  if (population >= 1_000) {
    return `${Math.round(population / 1_000)}K`;
  }

  return population.toLocaleString();
}

function formatCoordinate(value, positiveSuffix, negativeSuffix) {
  const coordinate = Number(value);

  if (!Number.isFinite(coordinate)) {
    return "—";
  }

  const suffix = coordinate >= 0 ? positiveSuffix : negativeSuffix;
  return `${Math.abs(coordinate).toFixed(4)}°${suffix}`;
}

export default function AirportDetail({ airport, onClose }) {
  if (!airport) {
    return null;
  }

  const aliases = airport.city_aliases ?? [];
  const matchTypes = airport.match_types ?? [];
  const subAirports = airport.sub_airports ?? [];
  const flag = flagEmoji(airport.country_code);
  const hasCoordinates = Number.isFinite(Number(airport.latitude)) && Number.isFinite(Number(airport.longitude));
  const mapsUrl = hasCoordinates
    ? `https://www.google.com/maps?q=${airport.latitude},${airport.longitude}`
    : null;

  return (
    <div className="detail-layer" role="dialog" aria-modal="true" aria-label={`${airport.iata} details`}>
      <button className="detail-backdrop" type="button" onClick={onClose} aria-label="Close detail" />

      <aside className="airport-detail">
        <header className="detail-header">
          <div>
            <span className="detail-iata">{airport.iata}</span>
            <h2>{airport.name}</h2>
            <p>
              {flag && <span>{flag}</span>} {airport.city}
              {airport.country && <span>, {airport.country}</span>}
            </p>
          </div>
          <button className="detail-close" type="button" onClick={onClose} aria-label="Close airport detail">
            ×
          </button>
        </header>

        <div className="detail-grid">
          <div className="info-tile">
            <span>📍 Region</span>
            <strong>{airport.region || "Not specified"}</strong>
          </div>
          <div className="info-tile">
            <span>🌍 Country</span>
            <strong>{airport.country}</strong>
          </div>
          <div className="info-tile">
            <span>🏷 Type</span>
            <strong>{typeLabel(airport.type)}</strong>
          </div>
          <div className="info-tile">
            <span>⭐ Priority Score</span>
            <strong>{airport.priority ?? 0}</strong>
          </div>
          <div className="info-tile">
            <span>🔤 IATA Code</span>
            <strong>{airport.iata}</strong>
          </div>
          <div className="info-tile">
            <span>📡 Matched via</span>
            <strong>{matchTypes.map((type) => MATCH_LABELS[type] ?? type).join(", ") || "Search"}</strong>
          </div>
          <div className="info-tile">
            <span>🌐 Latitude</span>
            <strong>{formatCoordinate(airport.latitude, "N", "S")}</strong>
          </div>
          <div className="info-tile">
            <span>🌐 Longitude</span>
            <strong>{formatCoordinate(airport.longitude, "E", "W")}</strong>
          </div>
          <div className="info-tile">
            <span>👑 Capital City</span>
            <strong>{airport.is_capital ? "👑 Yes" : "No"}</strong>
          </div>
          <div className="info-tile">
            <span>👥 City Population</span>
            <strong>{formatPopulation(airport.city_population)}</strong>
          </div>
        </div>

        <section className="detail-section detail-map-section">
          <h3>Location</h3>
          {mapsUrl ? (
            <a className="maps-link" href={mapsUrl} target="_blank" rel="noreferrer">
              <span aria-hidden="true">📍</span>
              View on Google Maps →
            </a>
          ) : (
            <span className="maps-link maps-link-disabled">
              <span aria-hidden="true">📍</span>
              Coordinates unavailable
            </span>
          )}
        </section>

        <section className="detail-section">
          <h3>Also known as</h3>
          <div className="alias-strip">
            {aliases.length > 0 ? (
              aliases.map((alias) => <span key={alias}>{alias}</span>)
            ) : (
              <span>No aliases returned</span>
            )}
          </div>
        </section>

        {airport.is_multi_airport_city && subAirports.length > 0 && (
          <section className="detail-section">
            <h3>Airports in this city</h3>
            <div className="detail-sub-list">
              {subAirports.map((subAirport) => (
                <div key={subAirport.iata} className="detail-sub-card">
                  <span>{subAirport.iata}</span>
                  <strong>{subAirport.name}</strong>
                </div>
              ))}
            </div>
          </section>
        )}

      </aside>
    </div>
  );
}
