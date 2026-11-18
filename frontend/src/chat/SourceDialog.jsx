import { useEffect, useRef } from "react";
import WrongFigure from "../WrongFigure.jsx";
import { Caption } from "./caption.jsx";

// "View source" window (P7-39; UC-07, BR-002): the figure enlarged with its caption, handbook and
// page, next to the stored image of the original handbook page, and a link that opens the FAA PDF
// at that page. The learner can flag the figure from here (UC-07 step 4 -> UC-03).
// A native <dialog>: Escape closes it, focus stays inside, and the page behind cannot be clicked.
// The two big images are only downloaded when the window is opened.
export default function SourceDialog({ result, query, onClose, onSessionExpired }) {
  const ref = useRef(null);

  useEffect(() => {
    const dialog = ref.current;
    if (result && !dialog.open) dialog.showModal();
    if (!result && dialog.open) dialog.close();
  }, [result]);

  // The link ends in "#page=N". Some PDF viewers ignore it, so the page is also written in the text.
  const pdfPage = result?.source_pdf_url?.match(/#page=(\d+)/)?.[1];

  return (
    <dialog
      ref={ref}
      className="source-dialog"
      aria-labelledby="source-title"
      onClose={onClose}
      onClick={(e) => e.target === ref.current && onClose()} // a click on the dark backdrop
    >
      {result && (
        <div className="source-inner">
          <header className="source-head">
            <div>
              <h2 id="source-title">
                <Caption caption={result.caption} figureNumber={result.figure_id} />
              </h2>
              <p className="plate-source">
                {result.handbook}, <span className="page">page {result.printed_page}</span>
              </p>
            </div>
            <button type="button" className="source-close" onClick={onClose} aria-label="Close">
              ×
            </button>
          </header>

          <div className="source-body">
            <section className="source-col">
              <h3>The figure</h3>
              <a href={result.image_url} target="_blank" rel="noopener noreferrer" className="source-img-link">
                <img src={result.image_url} alt={result.caption} />
              </a>
              {result.passage && <p className="source-passage">{result.passage}</p>}
            </section>
            <section className="source-col">
              <h3>The handbook page</h3>
              {result.page_image_url ? (
                <a href={result.page_image_url} target="_blank" rel="noopener noreferrer" className="source-img-link">
                  <img src={result.page_image_url} alt={`${result.handbook}, page ${result.printed_page}`} loading="lazy" />
                </a>
              ) : (
                <p className="notice">No image of this page was stored.</p>
              )}
              <p className="source-note">
                Page {result.printed_page} as printed in the handbook.{" "}
                {result.source_pdf_url && (
                  <a href={result.source_pdf_url} target="_blank" rel="noopener noreferrer">
                    Open the FAA PDF{pdfPage ? ` at PDF page ${pdfPage}` : ""}
                  </a>
                )}
              </p>
            </section>
          </div>

          <footer className="source-foot">
            <WrongFigure figureId={result.id} query={query} onSessionExpired={onSessionExpired} />
            <button type="button" className="btn" onClick={onClose}>Back to the answer</button>
          </footer>
        </div>
      )}
    </dialog>
  );
}
