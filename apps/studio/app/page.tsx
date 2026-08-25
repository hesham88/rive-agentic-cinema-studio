import Link from 'next/link';
import { Opening } from './Opening';
import { Why } from './Why';
import { Process } from './Process';
import { Engines } from './Engines';
import { KitShowcase } from './KitShowcase';
import { Gallery } from './Gallery';
import { Proof } from './Proof';
import { ShotList } from './ShotList';

/**
 * The landing surface.
 *
 * A judge scans this in about ninety seconds, so it is ordered by what has to
 * land first: the claim, proved immediately by the artefact running behind it;
 * then how it works; then what it is made of; then the interface as evidence
 * the craft goes all the way down; then the work itself, playing.
 *
 * The page is laid out as a shot list because the camera engine emits one. That
 * makes the numbering structural rather than decorative — each section consumes
 * what the previous produced.
 */
export default function Home() {
  return (
    <div className="min-h-dvh">
      <ShotList />

      <header className="fixed inset-x-0 top-0 z-50 border-b border-rule/60 bg-room/70 backdrop-blur-md">
        <div className="mx-auto flex max-w-[1400px] items-center justify-between gap-6 px-6 py-3.5 lg:pl-[224px]">
          <span className="display text-[17px] tracking-tight">Rive Agentic Studio</span>
          <nav className="flex items-center gap-1">
            <a
              href="#engines"
              className="nav-link hidden px-3 py-1.5 sm:inline"
            >
              engines
            </a>
            <a
              href="#kit"
              className="nav-link hidden px-3 py-1.5 sm:inline"
            >
              interface
            </a>
            <Link
              href="/inspect"
              className="btn btn-ghost !py-1.5 !text-[12px]"
            >
              inspector →
            </Link>
          </nav>
        </div>
      </header>

      <main>
        <Opening />
        <Why />
        <Process />
        <Engines />
        <Gallery />
        <KitShowcase />
        <Proof />
      </main>

      <footer id="close" className="rule-t">
        <div className="mx-auto max-w-[1400px] px-6 py-16 lg:pl-[224px]">
          <p className="display max-w-[20ch] text-[clamp(1.75rem,3.5vw,2.5rem)]">
            Describe it. <em>Then watch it ship.</em>
          </p>
          <div className="mt-10 flex flex-wrap items-baseline justify-between gap-4 rule-t pt-6">
            <p className="text-[13px] text-dim">
              Built with Gemini, Parallel and the Rive editor, driven over MCP.
            </p>
            <p className="num text-[11px] text-dim/60">MIT</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
