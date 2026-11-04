// One search result: figure, caption, source passage, handbook name + printed page.
// React escapes all text, so handbook text is never parsed as HTML.
export default function ResultCard({ result }) {
  return (
    <article className="card">
      <img src={result.image_url} alt={result.caption} loading="lazy" />
      <h2 className="caption">{result.caption}</h2>
      {result.passage && <p className="passage">{result.passage}</p>}
      <p className="source">
        {result.handbook}, page {result.printed_page}
      </p>
    </article>
  );
}
