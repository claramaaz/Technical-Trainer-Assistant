import { useState } from "react";

// "View source" (UC-07): the stored image of the handbook page the figure is on, so the
// learner can compare, and a link that opens the FAA PDF at that page. The page image is
// only downloaded when the learner asks for it.
export default function ViewSource({ result }) {
  const [open, setOpen] = useState(false);
  if (!result.page_image_url && !result.source_pdf_url) return null;
  // The link ends in "#page=N". Some PDF viewers (e.g. the Adobe Acrobat extension for Chrome)
  // ignore it and open at page 1, so the page is also written in the link text.
  const pdfPage = result.source_pdf_url?.match(/#page=(\d+)/)?.[1];
  return (
    <div className="view-source">
      {result.page_image_url && (
        <button type="button" className="source-toggle" aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Hide source page" : "View source"}
        </button>
      )}
      {result.source_pdf_url && (
        <a className="pdf-link" href={result.source_pdf_url} target="_blank" rel="noopener noreferrer">
          Open the FAA PDF{pdfPage ? ` (PDF page ${pdfPage})` : ""}
        </a>
      )}
      {open && (
        <figure className="source-page">
          <img
            src={result.page_image_url}
            alt={`${result.handbook}, page ${result.printed_page}`}
            loading="lazy"
          />
          <figcaption>
            {result.handbook}, page {result.printed_page} (as printed in the handbook)
          </figcaption>
        </figure>
      )}
    </div>
  );
}
