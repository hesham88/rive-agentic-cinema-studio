'use client';

import { useReveal } from './useScrollProgress';

/**
 * Why this exists — the section written for the Rive community, not for judges.
 *
 * In April 2026 Rive made their Agent free for everyone, framing it as
 * "AI should make it easier for anyone to learn and build in Rive, regardless
 * of plan." The three things their community asked for next were MCP
 * connections, bring-your-own API keys, and external agent integration.
 *
 * That is exactly what this is. The framing matters: Rive's Agent helps you
 * build faster INSIDE the editor; this builds the file FOR you and hands it
 * back. Complementary, not competing — and saying so plainly is more credible
 * than positioning against a tool the audience already likes.
 */

const CLAIMS = [
  {
    k: 'Your keys, your models',
    v: 'Gemini for the art, Parallel for the research, Lyria for the score. Nothing is metered by us because nothing runs on us.',
  },
  {
    k: 'Driven over MCP',
    v: 'The editor is the renderer. Artboards, shapes, rigs, timelines and state machines are all authored through its own protocol.',
  },
  {
    k: 'Or no editor at all',
    v: 'The format is implemented directly, so a file can be written byte by byte in the browser. A toggle is 667 bytes and needs nothing installed.',
  },
] as const;

export function Why() {
  const head = useReveal<HTMLDivElement>();

  return (
    <section id="why" className="relative">
      <div className="mx-auto max-w-[1400px] px-6 py-28 lg:pl-[224px]">
        <div className="grid gap-14 lg:grid-cols-[1fr_minmax(0,520px)] lg:gap-16">
          <div ref={head} className="reveal">
            <p className="eyebrow">For the people who already love Rive</p>
            <h2 className="display mt-4 text-[clamp(2rem,4.5vw,3.25rem)]">
              The three things you asked for, <em>built.</em>
            </h2>
            <p className="mt-6 max-w-[52ch] text-[16px] leading-relaxed text-read">
              When Rive made their Agent free in April, the replies asked for the same
              three things: MCP connections, bring your own API keys, and a way to point
              an outside agent at the editor.
            </p>
            <p className="mt-4 max-w-[52ch] text-[15px] leading-relaxed text-dim">
              Their Agent helps you build faster inside the editor. This one builds the
              file and hands it back — researched, drawn, traced, rigged, animated and
              exported, from a sentence. Different job, same tool, and it is open source.
            </p>
          </div>

          <dl className="grid gap-px overflow-hidden rounded-sm bg-rule">
            {CLAIMS.map((c, i) => (
              <Claim key={c.k} claim={c} index={i} />
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}

function Claim({ claim, index }: { claim: (typeof CLAIMS)[number]; index: number }) {
  // Staggered by a touch under five frames at 60fps — the offset a hand-animated
  // group uses so a list reads as arriving rather than appearing.
  const ref = useReveal<HTMLDivElement>(index * 70);
  return (
    <div ref={ref} className="reveal bg-panel p-6">
      <dt className="flex items-baseline gap-3">
        <span className="num text-[10px] text-lamp">{String(index + 1).padStart(2, '0')}</span>
        <span className="text-[15px] font-medium text-bright">{claim.k}</span>
      </dt>
      <dd className="mt-2.5 pl-8 text-[14px] leading-relaxed text-read">{claim.v}</dd>
    </div>
  );
}
