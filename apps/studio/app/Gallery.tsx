'use client';

import { Fit, Layout, useRive } from '@rive-app/react-webgl2';
import { useReveal } from './useReveal';

/**
 * The gallery.
 *
 * Every tile is the real `.riv` running, not a thumbnail — a screenshot of an
 * interactive asset proves nothing. The interactive ones say so, because a
 * visitor who does not know to hover will never find out.
 */

interface Piece {
  file: string;
  artboard?: string;
  stateMachine?: string;
  animation?: string;
  title: string;
  detail: string;
  bytes: number;
  facts: string[];
  interactive?: string;
}

const PIECES: Piece[] = [
  {
    file: '/riv/scene.riv',
    artboard: 'Scene',
    animation: 'CameraMove',
    title: 'Night launch',
    detail:
      'A parallax world — sky, moon, stars, two ridgelines — with a generated rocket and a four-shot camera move.',
    bytes: 39721,
    facts: ['14 shapes', '20 camera keys', '4 shots'],
  },
  {
    file: '/riv/paper-plane-interactive.riv',
    stateMachine: 'State Machine 1',
    title: 'Paper plane',
    detail:
      'The first thing this studio ever made. Idle float, hover response, driven by a bound boolean.',
    bytes: 1848,
    facts: ['4 shapes', '48 keys', '2 timelines'],
    interactive: 'Hover the canvas',
  },
  {
    file: '/riv/widget.riv',
    artboard: 'Widget',
    stateMachine: 'State Machine 1',
    title: 'Launch control',
    detail:
      'Text bound to a view model, with four timelines on one object entered by three different signals.',
    bytes: 37148,
    facts: ['bound text', '4 timelines', '3 triggers'],
    interactive: 'Hover, then press',
  },
];

function Tile({ piece, index }: { piece: Piece; index: number }) {
  const ref = useReveal<HTMLElement>(index * 90);

  const { RiveComponent } = useRive({
    src: piece.file,
    artboard: piece.artboard,
    stateMachines: piece.stateMachine,
    animations: piece.animation,
    autoplay: true,
    // Contain, not cover: these artboards have different aspect ratios (the
    // widget is 420x180, the scene 1000x600) and cropping a generated asset to
    // fit a grid hides the thing the tile exists to show.
    layout: new Layout({ fit: Fit.Contain }),
  });

  return (
    <article ref={ref} className="reveal glass-thin group flex flex-col overflow-hidden">
      <div className="relative">
        <div className="aspect-[4/3] w-full">
          <RiveComponent className="h-full w-full" />
        </div>
        {piece.interactive && (
          <p className="num pointer-events-none absolute bottom-2 right-2 rounded-md border border-white/10 bg-void/70 px-2 py-1 text-[10px] text-flame backdrop-blur">
            {piece.interactive}
          </p>
        )}
      </div>

      <div className="flex flex-1 flex-col border-t border-white/8 p-5">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-base font-semibold text-paper">{piece.title}</h3>
          <span className="num text-xs text-slate">
            {piece.bytes.toLocaleString()} B
          </span>
        </div>
        <p className="mt-1.5 text-sm leading-relaxed text-slate">{piece.detail}</p>
        <ul className="mt-4 flex flex-wrap gap-x-3 gap-y-1 pt-1">
          {piece.facts.map((f) => (
            <li key={f} className="num text-[11px] text-slate/60">
              {f}
            </li>
          ))}
        </ul>
      </div>
    </article>
  );
}

export function Gallery() {
  const head = useReveal<HTMLDivElement>();

  return (
    <section id="gallery" className="relative border-t border-white/8">
      <div className="aurora" aria-hidden />
      <div className="relative z-10 mx-auto max-w-6xl px-6 py-24">
        <div ref={head} className="reveal">
          <p className="eyebrow">Running, not pictured</p>
          <h2 className="display mt-3 max-w-2xl text-[clamp(1.75rem,3.5vw,2.5rem)]">
            Every piece here is live.
          </h2>
          <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-slate">
            Each tile is the actual file playing in your browser. Load any of them into
            the inspector to see their artboards, state machines and bound properties.
          </p>
        </div>

        <div className="mt-12 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {PIECES.map((p, i) => (
            <Tile key={p.file} piece={p} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}
