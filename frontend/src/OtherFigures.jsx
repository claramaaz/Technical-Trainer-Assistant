import WrongFigure from "./WrongFigure.jsx";

// The other returned figures, folded away under the main one (the brief asks for "the diagram",
// so one figure is shown large). Their thumbnails are only requested once the section is
// opened, so a learner on a slow connection does not pay for figures they never look at.
export default function OtherFigures({ results, open, onToggle, query, onSessionExpired }) {
  if (results.length === 0) return null;
  return (
    <section className="others">
      <button type="button" className="others-toggle" aria-expanded={open} onClick={onToggle}>
        {open ? "▾" : "▸"} Other possible figures ({results.length})
      </button>
      {open && (
        <ul className="others-list">
          {results.map((r) => (
            <li key={r.id} id={`fig-${r.id}`} className="other">
              <a href={r.image_url} target="_blank" rel="noopener noreferrer" className="other-thumb-link">
                <img
                  className="other-thumb"
                  src={r.thumbnail_url || r.image_url}
                  alt={r.caption}
                  loading="lazy"
                  decoding="async"
                />
              </a>
              <div className="other-body">
                <p className="source">
                  <span className="figure-number">Figure {r.figure_id}</span>
                  {r.handbook}, page {r.printed_page}
                </p>
                <p className="other-caption">{r.caption}</p>
                <WrongFigure figureId={r.id} query={query} onSessionExpired={onSessionExpired} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
