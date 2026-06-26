/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    // StockX product images are served from imgix; allow them for next/image.
    remotePatterns: [
      { protocol: "https", hostname: "stockx-assets.imgix.net" },
      { protocol: "https", hostname: "images.stockx.com" },
      { protocol: "https", hostname: "**.imgix.net" },
    ],
  },
};

module.exports = nextConfig;
