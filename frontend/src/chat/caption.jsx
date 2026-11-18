// The stored caption already starts with the handbook's own label ("Figure 5-2. Force vectors...").
// Split it so the label can be set in bold, as the FAA handbooks print it, without writing it twice.
// A caption without that label gets one built from the figure number.
const LABEL = /^(Figure\s+[\w.-]+?\.)\s*(.*)$/s;

export function splitCaption(caption = "", figureNumber) {
  const m = caption.match(LABEL);
  if (m) return { label: m[1], text: m[2] };
  return { label: figureNumber ? `Figure ${figureNumber}.` : "", text: caption };
}

export function Caption({ caption, figureNumber }) {
  const { label, text } = splitCaption(caption, figureNumber);
  return (
    <>
      {label && <strong>{label}</strong>} {text}
    </>
  );
}
