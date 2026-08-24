'use client';

import { Fit, Layout, useRive } from '@rive-app/react-webgl2';
import { useReveal } from './useScrollProgress';

/**
 * Running, not pictured.
 *
 * Every tile is the actual `.riv` playing in the visitor's browser. A
 * screenshot of an interactive asset proves nothing, which is the whole reason
 * this section exists rather than a carousel of images.
 *
 * The interactive ones say they are interactive, because a visitor who does not
 * know to hover never finds out.
 */

interface Piece {
  file: string;
  artboard?: string;
  stateMachine?: string;
  title: string;
  detail: string;
  bytes: number;
  facts: readonly string[];
  hint?: string;
}

const PIECES: readonly Piece[] = [
  {
    file: '/riv/scene.riv',
    artboard: 'Scene',
    stateMachine: 'State Machine 1',
    title: 'Night launch',
    detail:
      'A parallax world with a generated rocket and a four-shot camera move — the piece playing at the top of this page.',
    bytes: 39721,
    facts: ['14 shapes', '20 camera keys', '4 shots'],
  },
  {
    file: '/riv/lantern.riv',
    artboard: 'light/lantern',
    stateMachine: 'State Machine 1',
    title: 'Lantern',
    detail:
      'The light engine. Candle temperature read off the blackbody curve, inverse-square falloff, and a flicker that never repeats yet renders identically every run.',
    bytes: 3484,
    facts: ['1900 K', '6 channels', 'seeded flicker'],
  },
  {
    file: '/riv/ui-kit.riv',
    artboard: 'ui/slider',
    stateMachine: 'State Machine 1',
    title: 'Interface kit',
    detail:
      'Eight controls in one 5.3 KB file — button, switch, slider, field, select, tabs, progress, panel. The interface further up this page is made of them.',
    bytes: 5323,
    facts: ['8 artboards', '21 channels', '5.3 KB'],
  },
] as const;

function Tile({ piece, index }: { piece: Piece; index: number }) {
  const ref = useReveal<HTMLElement>(index * 80);

  const { RiveComponent } = useRive({
    src: piece.file,
    artboard: piece.artboard,
    stateMachines: piece.stateMachine,
    autoplay: true,
    autoBind: true,
    // Contain, not cover: these artboards have different aspect ratios, and
    // cropping a generated asset hides the thing the tile exists to show.
    layout: new Layout({ fit: Fit.Contain }),
  });

  return (
    <article ref={ref} className="reveal flex flex-col">
      <div className="panel relative overflow-hidden">
        <div className="aspect-[4/3] w-full">
          <RiveComponent className="h-full w-full" />
        </div>
        {piece.hint && (
          <p className="num pointer-events-none absolute bottom-2.5 right-2.5 rounded-sm border border-rule bg-room/80 px-2 py-1 text-[10px] text-ember">
            {piece.hint}
          </p>
        )}
      </div>

      <div className="mt-5">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-[15px] font-medium text-bright">{piece.title}</h3>
          <span className="num text-[11px] text-dim">
            {piece.bytes.toLocaleString()} B
          </span>
        </div>
        <p className="mt-2 text-[14px] leading-relaxed text-read">{piece.detail}</p>
        <ul className="mt-3.5 flex flex-wrap gap-x-3 gap-y-1">
          {piece.facts.map((f) => (
            <li key={f} className="num text-[11px] text-dim">
              {f}
            </li>
          ))}
        </ul>
      </div>
    </article>
  );
}

export function Proof() {
  const head = useReveal<HTMLDivElement>();

  return (
    <section id="proof" className="relative">
      <div className="mx-auto max-w-[1400px] px-6 py-28 lg:pl-[224px]">
        <div ref={head} className="reveal max-w-[54ch]">
          <p className="eyebrow">Running, not pictured</p>
          <h2 className="display mt-4 text-[clamp(2rem,4.5vw,3.25rem)]">
            Every piece here is <em>live.</em>
          </h2>
          <p className="mt-5 text-[15px] leading-relaxed text-read">
            Each tile is the real file playing in your browser. Load any of them into the
            inspector to see their artboards, state machines and bound properties.
          </p>
        </div>

        <div className="mt-14 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {PIECES.map((p, i) => (
            <Tile key={p.file} piece={p} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}
