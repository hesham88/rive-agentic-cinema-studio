import type { Metadata } from 'next';
import { Space_Grotesk, IBM_Plex_Sans, IBM_Plex_Mono } from 'next/font/google';
import './globals.css';

// Display: technical, slightly quirky grotesque. Not Inter — this product is
// about motion and machinery, and the display face should say so.
const display = Space_Grotesk({
  subsets: ['latin'],
  variable: '--font-display',
  weight: ['500', '700'],
});

const body = IBM_Plex_Sans({
  subsets: ['latin'],
  variable: '--font-body',
  weight: ['400', '500', '600'],
});

// Load-bearing, not ornamental. This product's texture IS numbers: frame 110,
// 80 paths, 37 KB, property key 16. They deserve a face that sets them well.
const mono = IBM_Plex_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  weight: ['400', '500'],
});

export const metadata: Metadata = {
  title: 'Rive Agentic Studio',
  description:
    'A sentence becomes a scene. Generated vector art, rigged, animated and shipped as interactive Rive.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
