/**
 * SeamDivider v2 - a slim animated gradient line with a moving shimmer
 * sweep (seam-red to bail-gold), replacing the stitched-hash pattern.
 * Same brand colors, much more premium/subtle feel.
 */
export default function SeamDivider({ className = "" }) {
  return (
    <div className={`relative h-[2px] w-full overflow-hidden rounded-full bg-white/10 ${className}`}>
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-seam to-transparent animate-[shimmer_2.8s_ease-in-out_infinite]" />
    </div>
  );
}