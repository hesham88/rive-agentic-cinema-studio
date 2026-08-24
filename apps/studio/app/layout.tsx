import type { Metadata } from 'next';
import { Instrument_Sans, Instrument_Serif, IBM_Plex_Mono } from 'next/font/google';
import './globals.css';

/**
 * A high-contrast serif for display, on warm-black.
 *
 * This is the decision the page's character rests on. Almost every dark
 * product page reaches for a grotesque, which is why they all look alike; a
 * serif at display size reads as a film title card instead. Instrument Serif
 * has the thin-to-thick contrast that survives at 80px and an italic worth
 * using — the two things a generic serif does not give you.
 */
const display = Instrument_Serif({
  subsets: ['latin'],
  variable: '--font-display',
  weight: ['400'],
  style: ['normal', 'italic'],
});

/** Its sans companion. Designed alongside the serif, so the pairing is real. */
const body = Instrument_Sans({
  subsets: ['latin'],
  variable: '--font-body',
  weight: ['400', '500', '600'],
});

/**
 * Load-bearing, not ornamental.
 *
 * This product's texture IS numbers: frame 110, 868 bytes, 4 shots, property
 * key 55. They are content, and they deserve a face that sets them properly
 * with tabular figures and a slashed zero.
 */
const mono = IBM_Plex_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  weight: ['400', '500'],
});

export const metadata: Metadata = {
  title: 'Rive Agentic Studio — a sentence becomes a scene',
  description:
    'Describe it. The studio researches how it is really drawn, generates the art, ' +
    'traces it to vector, rigs it, animates it, scores it, and ships an interactive ' +
    'file the web can run.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
