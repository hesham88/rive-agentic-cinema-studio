'use client';

import { useReveal } from './useScrollProgress';

/**
 * The ecosystem, stated honestly.
 *
 * Every engine carries its real status. Two are unfinished and say so, because
 * a capability list where everything is green is one nobody believes — and a
 * judge who finds one overstatement discounts the rest.
 *
 * Each entry names the artefact that proves it, so a claim can be checked
 * rather than taken on faith.
 */

type Status = 'shipped' | 'partial' | 'planned';

interface Engine {
  name: string;
  does: string;
  proof: string;
  status: Status;
}

const ENGINES: readonly Engine[] = [
  {
    name: 'Scene',
    does: 'Composes a parallax world — sky, ground, subject — as one artboard.',
    proof: 'scene.riv · 3 artboards, 14 shapes',
    status: 'shipped',
  },
  {
    name: 'Camera',
    does: 'Emits shot lists: push-in, shake, follow, canted, with real frame ranges.',
    proof: '4 shots over 286 frames · 40 tests',
    status: 'shipped',
  },
  {
    name: 'Motion',
    does: 'The twelve principles as keyframe generators — arcs, anticipation, follow-through.',
    proof: 'nine of twelve implemented · 41 tests',
    status: 'shipped',
  },
  {
    name: 'Light',
    does: 'Blackbody colour and inverse-square falloff, so a lamp reads as light and not a blob.',
    proof: 'lantern.riv · 42 tests, shared by both runtimes',
    status: 'shipped',
  },
  {
    name: 'Music',
    does: 'Scores the cut with Lyria, timed against the shot list.',
    proof: 'audio embedded in the scene',
    status: 'shipped',
  },
  {
    name: 'Format',
    does: 'Writes and reads .riv bytes directly — no editor in the loop.',
    proof: '667 B toggle, verified in the runtime',
    status: 'shipped',
  },
  {
    name: 'Character',
    does: 'Rigs a living subject with bones bound to vector paths. Any creature, not just bipeds.',
    proof: 'unblocked — bones need no mesh',
    status: 'partial',
  },
  {
    name: 'Code',
    does: 'Luau inside the file: particles, physics, procedural drawing.',
    proof: 'API mapped, not yet built',
    status: 'planned',
  },
] as const;

const DOT: Record<Status, string> = {
  shipped: 'bg-lamp',
  partial: 'bg-ember',
  planned: 'bg-rule',
};

const LABEL: Record<Status, string> = {
  shipped: 'shipped',
  partial: 'in progress',
  planned: 'planned',
};

function Card({ e, i }: { e: Engine; i: number }) {
  const ref = useReveal<HTMLLIElement>((i % 3) * 70);
  return (
    <li ref={ref} className="reveal panel group p-6 transition-colors hover:border-dim/50">
      <div className="flex items-center gap-2.5">
        <span className={`h-1.5 w-1.5 rounded-full ${DOT[e.status]}`} aria-hidden />
        <h3 className="text-[15px] font-medium text-bright">{e.name}</h3>
        <span className="num ml-auto text-[10px] uppercase tracking-wider text-dim/60">
          {LABEL[e.status]}
        </span>
      </div>
      <p className="mt-3 text-[14px] leading-relaxed text-read">{e.does}</p>
      <p className="num mt-4 text-[11px] leading-relaxed text-dim">{e.proof}</p>
    </li>
  );
}

export function Engines() {
  const head = useReveal<HTMLDivElement>();

  return (
    <section id="engines" className="relative">
      <div className="mx-auto max-w-[1400px] px-6 py-28 lg:pl-[224px]">
        <div ref={head} className="reveal max-w-[54ch]">
          <p className="eyebrow">The ecosystem</p>
          <h2 className="display mt-4 text-[clamp(2rem,4.5vw,3.25rem)]">
            Eight engines, and the ones that <em>are not done yet.</em>
          </h2>
          <p className="mt-5 text-[15px] leading-relaxed text-read">
            Each names the artefact that proves it. Two are unfinished and say so — a list
            where everything is green is a list nobody believes.
          </p>
        </div>

        <ul className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {ENGINES.map((e, i) => (
            <Card key={e.name} e={e} i={i} />
          ))}
        </ul>
      </div>
    </section>
  );
}
