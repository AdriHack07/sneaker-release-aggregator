import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Sneaker Flip Radar",
  description: "Profitable upcoming sneaker releases, refreshed daily.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <div className="inner">
            <Link href="/">
              <h1>👟 Sneaker Flip Radar</h1>
            </Link>
            <span className="sub">
              Profitable upcoming releases · next 60 days · refreshed daily
            </span>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
