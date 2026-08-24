import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // rive-engine ships TypeScript source (its exports map points at src/), so the
  // app's bundler compiles it rather than consuming a prebuilt dist.
  transpilePackages: ['rive-engine'],

  // Every route prerenders to static HTML (verified: next build reports all
  // routes as Static), so the studio deploys to a CDN with no server. Firebase
  // Auth is client-side, so authentication still works.
  output: 'export',
  images: { unoptimized: true },
};

export default nextConfig;
