import { useEffect, useState } from "react";
import WrongFigure from "../WrongFigure.jsx";
import { Caption } from "./caption.jsx";

// The main figure of an answer (UC-02 step 6): the handbook's own image, its caption as the handbook
// prints it, the handbook and printed page, "View source" (UC-07) and "Wrong figure" (UC-03).
//
// UC-02 A4 / NFR-001: the text is painted first; the image request starts one frame later, with a
// placeholder of the same size so nothing jumps. The thumbnail is used when there is one; the
// enlarged figure is one tap away (View source). BR-002: caption, handbook and page stay visible
// even if the image fails.
export default function FigurePlate({ result, query, onOpenSource, onSessionExpired }) {
  const [start, setStart] = useState(false);
  const [state, setState] = useState("loading"); // loading | loaded | failed

  useEffect(() => {
    const frame = requestAnimationFrame(() => setStart(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <figure className="plate answer-plate" id={`fig-${result.id}`}>
      {state === "failed" ? (
        <p className="plate-placeholder" role="status">
          The figure could not be loaded. Its caption and page below still identify it.
        </p>
      ) : (
        <button
          type="button"
          className="plate-image"
          onClick={() => onOpenSource(result)}
          aria-label={`Enlarge figure ${result.figure_id || ""} and view its source page`}
        >
          {state === "loading" && <span className="plate-placeholder pulse" aria-hidden="true">Loading figure…</span>}
          {start && (
            <img
              src={result.thumbnail_url || result.image_url}
              alt={result.caption}
              decoding="async"
              hidden={state !== "loaded"}
              onLoad={() => setState("loaded")}
              onError={() => setState("failed")}
            />
          )}
        </button>
      )}
      <figcaption className="plate-text">
        <p className="plate-caption">
          <Caption caption={result.caption} figureNumber={result.figure_id} />
        </p>
        <p className="plate-source">
          {result.handbook}, <span className="page">page {result.printed_page}</span>
        </p>
        <div className="plate-actions">
          <button type="button" className="btn btn-quiet btn-small" onClick={() => onOpenSource(result)}>
            View source
          </button>
          <WrongFigure figureId={result.id} query={query} onSessionExpired={onSessionExpired} />
        </div>
      </figcaption>
    </figure>
  );
}
