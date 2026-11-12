import { useEffect, useState } from "react";

// One search result: caption, handbook name + printed page, source passage, then the figure.
// React escapes all text, so handbook text is never parsed as HTML.
//
// UC-02 A4 / NFR-001: on a slow connection the text is shown first. The figure request only
// starts after the text has been painted, and a placeholder of the same size keeps the layout
// from jumping. The small thumbnail is used when the server has one; the full image stays
// one tap away. BR-002: caption, handbook and page stay visible even if the image fails.
export default function ResultCard({ result }) {
  const [startImage, setStartImage] = useState(false);
  const [imageState, setImageState] = useState("loading"); // loading | loaded | failed

  useEffect(() => {
    // Wait one frame so the browser paints the text before it starts downloading the image.
    const frame = requestAnimationFrame(() => setStartImage(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  const src = result.thumbnail_url || result.image_url;
  const figureLabel = result.figure_id ? `Figure ${result.figure_id}` : "Figure";

  return (
    <article className="card">
      <p className="source">
        <span className="figure-number">{figureLabel}</span>
        {result.handbook}, page {result.printed_page}
      </p>
      <h2 className="caption">{result.caption}</h2>
      {result.passage && <p className="passage">{result.passage}</p>}

      <div className={`figure figure-${imageState}`}>
        {imageState === "loading" && (
          <div className="placeholder" aria-hidden="true">
            Loading figure…
          </div>
        )}
        {imageState === "failed" && (
          <p className="figure-error" role="status">
            The figure could not be loaded. The caption and page above still identify it.
          </p>
        )}
        {startImage && imageState !== "failed" && (
          <img
            src={src}
            alt={result.caption}
            decoding="async"
            onLoad={() => setImageState("loaded")}
            onError={() => setImageState("failed")}
          />
        )}
      </div>

      {result.thumbnail_url && imageState === "loaded" && (
        <a className="full-size" href={result.image_url} target="_blank" rel="noopener noreferrer">
          Open full-size figure
        </a>
      )}
    </article>
  );
}
