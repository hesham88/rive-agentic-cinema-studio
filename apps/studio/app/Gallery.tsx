'use client';

import Image from 'next/image';
import { useState } from 'react';
import manifest from './art-manifest.json';
import { useReveal } from './useScrollProgress';

/**
 * The library, shown rather than described.
 *
 * Every other section of this page makes a claim in prose. This one is the
 * only place a visitor can look at the material the pipeline actually has, so
 * it is deliberately the least written and the most shown.
 *
 * These are the SOURCED pieces — openly licensed vectors found and gated by the
 * pipeline's own discovery stage, not art this project drew. That distinction
 * is stated on the section rather than glossed, because a showcase that implies
 * it generated someone else's work is worth less than nothing. Attribution is
 * on every tile for the same reason: these are CC0 and public-domain files, and
 * crediting the artist costs one line.
 *
 * Rendered as <img> rather than inlined. Sixteen inlined SVGs would put a
 * megabyte of markup in the document and block first paint; as images they are
 * cached, lazily fetched, and the browser decodes them off the main thread.
 */

type Piece = (typeof manifest)[number];

const TOTAL_PATHS = manifest.reduce((n, p) => n + p.paths, 0);

export function Gallery() {
  const head = useReveal<HTMLDivElement>();
  const [active, setActive] = useState<Piece | null>(null);

  return (
    <section id="library" className="relative border-t border-rule">
      <div className="mx-auto max-w-[1400px] px-6 py-24 lg:pl-[224px]">
        <div ref={head} className="reveal">
          <p className="eyebrow">Sourced, licensed, gated</p>
          <h2 className="display mt-3 max-w-3xl text-[clamp(1.75rem,3.5vw,2.5rem)]">
            A library the pipeline <em>found</em> for itself.
          </h2>
          <p className="mt-4 max-w-[58ch] text-[15px] leading-relaxed text-read">
            Research finds the art, a licence gate refuses anything share-alike or
            unlicensed, a second gate refuses trademarks, and every file is stripped of
            script and external references before it is written to disk. These{' '}
            {manifest.length} pieces carry {TOTAL_PATHS.toLocaleString()} vector paths
            between them.
          </p>
          <p className="mt-3 max-w-[58ch] text-[14px] leading-relaxed text-dim">
            Drawn by other people and released under CC0 or into the public domain —
            credited below, as the licences ask. What this studio generates is elsewhere
            on the page.
          </p>
        </div>

        <ul className="mt-12 grid grid-cols-2 gap-px overflow-hidden rounded-sm bg-rule sm:grid-cols-3 lg:grid-cols-4">
          {manifest.map((piece, i) => (
            <Tile
              key={piece.file}
              piece={piece}
              index={i}
              onOpen={() => setActive(piece)}
            />
          ))}
        </ul>
      </div>

      {active && <Credit piece={active} onClose={() => setActive(null)} />}
    </section>
  );
}

function Tile({
  piece,
  index,
  onOpen,
}: {
  piece: Piece;
  index: number;
  onOpen: () => void;
}) {
  // Staggered by a touch under five frames at 60fps — the offset a
  // hand-animated group uses so a grid reads as arriving, not appearing.
  const ref = useReveal<HTMLLIElement>((index % 4) * 70 + Math.floor(index / 4) * 40);

  return (
    <li ref={ref} className="reveal group relative bg-panel">
      <button
        type="button"
        onClick={onOpen}
        className="flex w-full flex-col items-stretch text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-signal"
        aria-label={`${piece.subject} — ${piece.paths} paths, ${piece.licence}. Show credit.`}
      >
        {/* A light plate under every piece.
            These come from many hands: some are flat colour, some are black
            line art drawn for paper. Line art on a near-black page is
            invisible, so a gallery of mixed provenance needs one consistent
            ground rather than a per-piece fix. The plate is warm and slightly
            off-white so it reads as a mount rather than a hole in the page. */}
        <span className="relative block aspect-square overflow-hidden bg-[#f4f1ea] p-5">
          <Image
            src={piece.file}
            alt={piece.subject}
            fill
            sizes="(min-width:1024px) 20vw, (min-width:640px) 30vw, 45vw"
            className="object-contain p-4 transition-transform duration-500 ease-out group-hover:scale-[1.06]"
            unoptimized
          />
        </span>
        <span className="flex items-baseline justify-between gap-2 border-t border-rule px-4 py-2.5">
          <span className="truncate text-[13px] text-read">{piece.subject}</span>
          <span className="num shrink-0 text-[10px] text-dim/60">{piece.paths}p</span>
        </span>
      </button>
    </li>
  );
}

function Credit({ piece, onClose }: { piece: Piece; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-room/80 p-4 backdrop-blur-sm sm:items-center"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="panel w-full max-w-md p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={`Credit for ${piece.subject}`}
      >
        <p className="eyebrow">Attribution</p>
        <p className="display mt-2 text-[20px]">{piece.title}</p>
        <dl className="mt-5 flex flex-col gap-2">
          {[
            ['artist', piece.artist],
            ['licence', piece.licence],
            ['paths', `${piece.paths}`],
            ['size', `${piece.kb} KB`],
          ].map(([k, v]) => (
            <div key={k} className="flex items-baseline justify-between gap-3">
              <dt className="num text-[11px] uppercase tracking-wider text-dim/60">{k}</dt>
              <dd className="num truncate text-[12px] text-bright">{v}</dd>
            </div>
          ))}
        </dl>
        {piece.source && (
          <a
            href={piece.source}
            target="_blank"
            rel="noreferrer noopener"
            className="num mt-5 inline-block text-[11px] text-signal underline-offset-4 hover:underline"
          >
            source →
          </a>
        )}
        <button
          type="button"
          onClick={onClose}
          className="num mt-6 w-full rounded-sm border border-rule py-2 text-[11px] text-read transition-colors hover:border-signal/60 hover:text-signal"
        >
          close
        </button>
      </div>
    </div>
  );
}
