export default function CricketStumpsBg({ className = "" }) {
  return (
    <svg
      viewBox="0 0 800 400"
      className={className}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
    >
      <rect x="0" y="0" width="800" height="400" fill="#0F1A14" />
      <ellipse cx="400" cy="230" rx="380" ry="60" fill="#16241D" opacity="0.6" />

      <g transform="translate(400, 150)">
        <rect x="-22" y="-90" width="8" height="90" rx="3" fill="#C9A876" className="anim-stump-mid" />
        <rect x="-4" y="-95" width="8" height="95" rx="3" fill="#C9A876" />
        <rect x="14" y="-90" width="8" height="90" rx="3" fill="#C9A876" className="anim-stump-mid" />

        <rect x="-20" y="-99" width="18" height="6" rx="3" fill="#D2A24C" className="anim-bail-left" />
        <rect x="2" y="-101" width="18" height="6" rx="3" fill="#D2A24C" className="anim-bail-right" />

        <circle cx="0" cy="-50" r="26" fill="#e7d8d6" className="anim-flash" />

<path
  d="M -420 -110 L 0 -50"
  stroke="#D2A24C"
  strokeWidth="2"
  strokeLinecap="round"
  fill="none"
  className="anim-trajectory"
/>

<g className="anim-ball">
  <circle cx="0" cy="-50" r="5" fill="#FFFFFF" />
<polyline points="-5,-50 -3.6,-52.9 -2.1,-50.7 -0.7,-53.6 0.7,-50.7 2.1,-52.9 3.6,-50.7 5,-50"
          stroke="#000000" strokeWidth="1" strokeLinejoin="round" strokeLinecap="round" fill="none" />
<polyline points="-5,-50 -3.6,-47.1 -2.1,-49.3 -0.7,-46.4 0.7,-49.3 2.1,-47.1 3.6,-49.3 5,-50"
          stroke="#000000" strokeWidth="1" strokeLinejoin="round" strokeLinecap="round" fill="none" />
</g>
      </g>
    </svg>
  );
}