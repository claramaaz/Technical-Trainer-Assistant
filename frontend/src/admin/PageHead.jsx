// Title, purpose and (optional) actions at the top of every admin page.
export default function PageHead({ page, children }) {
  return (
    <header className="page-head">
      <div>
        <h1>{page.title}</h1>
        <p className="admin-lead">{page.purpose}</p>
      </div>
      {children}
    </header>
  );
}
