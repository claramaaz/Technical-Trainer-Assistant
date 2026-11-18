import { LogoMark, Wordmark } from "../Logo.jsx";
import "./public.css";

// Public landing page (Clara's design brief: short landing + ONE login page; no sign-up, because
// accounts and roles are created by an Admin with ingestion/create_user.py).
export default function Landing() {
  return (
    <div className="public">
      <header className="public-top">
        <Wordmark />
        <a className="btn" href="#/login">Log in</a>
      </header>

      <main className="hero">
        <div className="hero-copy">
          <h1>Ask the handbook. Get&nbsp;the&nbsp;diagram.</h1>
          <p className="hero-lead">
            FlightWise answers technical questions from the FAA training handbooks with the
            explanation, the actual figure and the handbook page it comes from, so you can always
            check the original.
          </p>
          <a className="btn hero-cta" href="#/login">Log in to ask a question</a>
          <p className="hero-note">Accounts are created by your instructor.</p>
        </div>

        <figure className="sample" aria-label="Example of an answer">
          <p className="sample-label">Example</p>
          <p className="sample-question">What are the four forces acting on an airplane in flight?</p>
          <p className="sample-answer">
            In steady flight, lift opposes weight and thrust opposes drag; the airplane is in
            equilibrium when the opposing forces are equal.{" "}
            <span className="fig-tag">Fig.</span>
          </p>
          <div className="plate plate-static">
            <FourForces />
            <div className="plate-text">
              <p className="plate-caption"><strong>Example figure.</strong> Forces acting on an airplane in flight.</p>
              <p className="plate-source">Pilot's Handbook of Aeronautical Knowledge</p>
            </div>
          </div>
        </figure>
      </main>

      <section className="facts" aria-label="What FlightWise does">
        <div>
          <h2>The real figure</h2>
          <p>The diagram is cut from the handbook page itself, with its own caption, never redrawn or described.</p>
        </div>
        <div>
          <h2>Every sentence cited</h2>
          <p>Each sentence of an answer links to the passage it comes from, with the handbook and printed page.</p>
        </div>
        <div>
          <h2>Built for a phone</h2>
          <p>The text arrives first and the figures follow, so it stays usable on a slow connection.</p>
        </div>
      </section>

      <footer className="public-foot">
        <LogoMark size={20} />
        <p>
          A training tool: answers are not operational aviation guidance. FAA handbooks are public-domain
          works of the United States Government. ESIB, Université Saint-Joseph, project P7.
        </p>
      </footer>
    </div>
  );
}

// A simple line drawing for the example only (the real answers show the handbook's own figure).
function FourForces() {
  return (
    <svg className="plate-svg" viewBox="0 0 320 180" role="img" aria-label="An airplane with lift, weight, thrust and drag arrows">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
          <path d="M0 0L10 5L0 10Z" fill="currentColor" />
        </marker>
      </defs>
      <g fill="none" stroke="currentColor" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round">
        {/* fuselage, wing and tail */}
        <path d="M108 96 C130 86 196 84 226 88 C240 90 248 94 248 98 C248 102 238 104 224 104 L120 104 C112 104 106 100 108 96Z" />
        <path d="M160 96 L188 96 L176 116 L156 116Z" />
        <path d="M112 96 L100 72 L112 72 L128 92" />
        <path d="M226 92 L236 92" />
        {/* forces */}
        <path d="M172 82 V28" markerEnd="url(#arrow)" />
        <path d="M172 118 V160" markerEnd="url(#arrow)" />
        <path d="M252 98 H300" markerEnd="url(#arrow)" />
        <path d="M104 98 H44" markerEnd="url(#arrow)" />
      </g>
      <g fill="currentColor" fontSize="13" fontWeight="600" fontFamily="inherit">
        <text x="182" y="36">Lift</text>
        <text x="182" y="158">Weight</text>
        <text x="262" y="88">Thrust</text>
        <text x="40" y="88">Drag</text>
      </g>
    </svg>
  );
}
