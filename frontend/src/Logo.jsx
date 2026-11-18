// FlightWise logo: an open book whose right-hand pages fan out into a wing. One colour
// (currentColor), so it is navy on white and white on the navy sidebar.
export function LogoMark({ size = 32, title }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="currentColor"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      aria-label={title}
    >
      {/* left page */}
      <path d="M15.2 27C11.6 24.4 7.4 23.6 2.5 24.2V10.4C7.4 9.8 11.6 10.9 15.2 13.8Z" />
      {/* right pages, opening into three wing feathers */}
      <path d="M16.8 13.6C20.9 9.7 25.2 6.6 30 4.2C29 8.4 25.3 12.4 16.8 17.4Z" />
      <path d="M16.8 19.3C21.1 16.1 25.4 14 29.6 12.9C28.3 16.4 24.1 19.5 16.8 22.6Z" />
      <path d="M16.8 24.6C20.5 22.6 24.4 21.6 28.4 21.4C26.6 24.4 22.6 26.4 16.8 27Z" />
    </svg>
  );
}

export function Wordmark({ size = 28, subtitle = true }) {
  return (
    <span className="wordmark">
      <LogoMark size={size} />
      <span className="wordmark-text">
        <span className="wordmark-name">FlightWise</span>
        {subtitle && <span className="wordmark-sub">Technical Training Assistant</span>}
      </span>
    </span>
  );
}
