'use client';

import Image from 'next/image';
import manifest from './art-manifest.json';

/**
 * The scattered tiles around the hero.
 *
 * Cosmos's move, and the reason it is worth borrowing: "imagery is the product,
 * not decoration". Small cropped tiles pinned around centred text at slight
 * rotations, like polaroids on a gallery wall. A studio whose claim is that it
 * produces artwork should show artwork above the fold — a single framed
 * viewport plus prose is a page describing a product rather than being one.
 *
 * Three rules keep it from becoming noise.
 *
 * It stays OUT of the reading column. Every tile is positioned in the outer
 * margins, so the headline and body never compete with an image for the same
 * pixels. The composition is a border, not a background.
 *
 * It stays QUIET. Tiles sit at 55% opacity and lift to 100% on hover; they are
 * peripheral vision, and the lit monitor remains the only fully saturated
 * element. That is the palette's own rule — saturated colour belongs to the
 * artwork, and the artwork the page is arguing for is the one that is running.
 *
 * It NEVER MOVES on its own. A drifting collage behind text is the single most
 * common way a "motion-graphics" landing page becomes unreadable. These are
 * still until pointed at.
 */

/** Rotations and positions are fixed, not random: a layout that reshuffles on
 *  every render cannot be judged, and cannot be fixed when it is wrong. */
/* The left edge starts at 15%, not 3%.
   The shot-list rail occupies the first 220px of the viewport and it is
   navigation — a decorative tile sitting on top of it hid two section labels
   outright. A collage may use the margins; it may not use the chrome. */
const TILES = [
  { pos: 'left-[16%] top-[12%]', size: 96, rot: -7 },
  { pos: 'left-[19%] bottom-[14%]', size: 78, rot: 5 },
  { pos: 'right-[4%] top-[9%]', size: 88, rot: 6 },
  { pos: 'right-[2%] bottom-[8%]', size: 104, rot: -5 },
  { pos: 'right-[3%] bottom-[44%]', size: 70, rot: 8 },
] as const;

export function HeroCollage() {
  // Widest pieces first — a collage reads better when the biggest tiles are the
  // most detailed ones, and path count is a fair proxy for detail here.
  const picks = [...manifest].sort((a, b) => b.paths - a.paths).slice(0, TILES.length);

  return (
    <div aria-hidden className="pointer-events-none absolute inset-0 hidden xl:block">
      {picks.map((piece, i) => {
        const t = TILES[i]!;
        return (
          <div
            key={piece.file}
            className={`pointer-events-auto absolute ${t.pos} opacity-55 transition-opacity duration-500 ease-out hover:opacity-100`}
            style={{ transform: `rotate(${t.rot}deg)`, width: t.size, height: t.size }}
          >
            {/* The same warm plate the gallery uses. These are mixed-provenance
                files and several are line art drawn for paper; on a blue-black
                canvas they would be invisible without a mount. */}
            <div className="relative h-full w-full overflow-hidden rounded-[12px] bg-paper p-2.5">
              <Image
                src={piece.file}
                alt=""
                fill
                sizes="120px"
                className="object-contain p-1"
                unoptimized
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
