import Link from 'next/link';
import { HeroStage } from './HeroStage';
import { ControlDeck } from './ControlDeck';
import { KitShowcase } from './KitShowcase';
import { Pipeline } from './Pipeline';
import { Gallery } from './Gallery';

/**
 * The landing surface.
 *
 * Its single job is to prove the claim immediately: a sentence became this, and
 * it is running in your browser right now. So the hero is the artefact itself,
 * playing full-bleed, with the copy floating over it.
 */
export default function Home() {
  return (
    <div className="min-h-dvh">
      <header className="sticky top-0 z-50 border-b border-white/8 bg-void/60 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-6 py-3.5">
          <div className="flex items-baseline gap-3">
            <span className="display text-lg tracking-tight">Rive Agentic Studio</span>
            <span className="eyebrow hidden sm:inline">web · cinema</span>
          </div>
          <nav className="flex items-center gap-1">
            <a
              href="#deck"
              className="num hidden rounded-md px-3 py-1.5 text-xs text-slate transition-colors hover:text-paper sm:inline"
            >
              controls
            </a>
            <a
              href="#kit"
              className="num hidden rounded-md px-3 py-1.5 text-xs text-slate transition-colors hover:text-paper sm:inline"
            >
              ui kit
            </a>
            <a
              href="#gallery"
              className="num hidden rounded-md px-3 py-1.5 text-xs text-slate transition-colors hover:text-paper sm:inline"
            >
              gallery
            </a>
            <Link
              href="/inspect"
              className="num rounded-md border border-white/15 px-3 py-1.5 text-xs text-slate transition-colors hover:border-flame/60 hover:text-flame"
            >
              open inspector →
            </Link>
          </nav>
        </div>
      </header>

      <main>
        {/* Hero: the artefact first, the claim over it. */}
        <section className="relative isolate min-h-[86vh] overflow-hidden">
          <HeroStage />

          <div className="relative z-20 mx-auto flex min-h-[86vh] max-w-6xl flex-col justify-center px-6 pb-64 pt-20">
            <div className="max-w-xl">
              <p className="eyebrow">Generated, not drawn</p>
              <h1 className="display mt-4 text-[clamp(2.5rem,6.5vw,4.5rem)]">
                A sentence
                <br />
                becomes a scene.
              </h1>
              <p className="mt-6 max-w-md text-[15px] leading-relaxed text-slate">
                Describe what you want. The studio researches how it is really drawn,
                generates the art, traces it to vector, rigs it, animates it, scores it,
                and exports an interactive file the web can run.
              </p>
              <p className="mt-4 max-w-md text-[15px] leading-relaxed text-slate">
                Everything on this page was made that way — including the scene playing
                behind these words, and its camera move.
              </p>

              <div className="mt-8 flex flex-wrap gap-3">
                <Link
                  href="/inspect"
                  className="rounded-md bg-ignite px-5 py-2.5 text-sm font-semibold text-void transition-colors hover:bg-flame"
                >
                  Inspect a file
                </Link>
                <a
                  href="#deck"
                  className="rounded-md border border-white/20 bg-white/5 px-5 py-2.5 text-sm font-medium text-paper backdrop-blur transition-colors hover:border-white/45"
                >
                  Drive the controls
                </a>
              </div>
            </div>
          </div>
        </section>

        <ControlDeck />
        <KitShowcase />
        <Pipeline />
        <Gallery />
      </main>

      <footer className="border-t border-white/8">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-8 text-xs text-slate">
          <span>
            Built with Gemini, Parallel Search and the Rive editor, driven over MCP.
          </span>
          <span className="num text-slate/60">MIT</span>
        </div>
      </footer>
    </div>
  );
}
