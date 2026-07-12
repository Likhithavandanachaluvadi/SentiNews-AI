import type { Metadata, Viewport } from "next";
import { Inter, Hanken_Grotesk } from "next/font/google";
import "./globals.css";
import { RootQueryProvider } from "@/lib/providers";

const inter = Inter({ subsets: ["latin"] });
const hankenGrotesk = Hanken_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "SentiNews AI - with AI",
  description:
    "Real-time institutional-grade stock analysis powered by autonomous AI research agents.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: true,
  viewportFit: "cover",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Hanken+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
        <link
          rel="stylesheet"
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap"
        />
      </head>
      <body
        className={`${inter.className} min-h-screen bg-background text-on-surface antialiased flex flex-col`}
        suppressHydrationWarning
      >
        {/* Header */}
        <header className="bg-surface/80 backdrop-blur-md w-full z-50 sticky top-0 border-b border-surface-container-highest">
          <div className="flex justify-between items-center w-full px-6 md:px-10 max-w-[1300px] mx-auto h-20">
            <div className="flex items-center gap-2">
              <span className="material-symbols-outlined text-google-blue symbol-filled text-3xl">
                insights
              </span>
              <span
                className={`${hankenGrotesk.className} font-headline-md text-headline-md font-bold text-primary dark:text-primary tracking-tight`}
              >
                SentiNews AI
              </span>
            </div>

            <nav className="hidden md:flex gap-8 items-center h-full">
              <a
                className="text-on-surface-variant dark:text-on-surface-variant font-medium hover:text-primary dark:hover:text-primary-fixed-dim transition-colors duration-200"
                href="#"
              >
                Markets
              </a>
              <a
                className="text-on-surface-variant dark:text-on-surface-variant font-medium hover:text-primary dark:hover:text-primary-fixed-dim transition-colors duration-200"
                href="#"
              >
                News
              </a>
              <a
                className="text-primary dark:text-primary border-b-2 border-primary pb-2 font-bold hover:text-primary dark:hover:text-primary-fixed-dim transition-colors duration-200 h-full flex items-center pt-2"
                href="#"
              >
                Research with AI
              </a>
              <a
                className="text-on-surface-variant dark:text-on-surface-variant font-medium hover:text-primary dark:hover:text-primary-fixed-dim transition-colors duration-200"
                href="#"
              >
                Education
              </a>
              <a
                className="text-on-surface-variant dark:text-on-surface-variant font-medium hover:text-primary dark:hover:text-primary-fixed-dim transition-colors duration-200"
                href="#"
              >
                Pricing
              </a>
            </nav>

            <div className="flex items-center gap-4">
              <button className="text-on-surface-variant font-label-lg text-label-lg hover:text-primary transition-colors">
                Sign In
              </button>
              <button className="bg-google-blue text-white px-6 py-2.5 rounded-full font-label-lg text-label-lg hover:bg-blue-600 transition-colors">
                Get Started
              </button>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <RootQueryProvider>
          <main className="flex-grow flex flex-col w-full">{children}</main>
        </RootQueryProvider>

        {/* Footer */}
        <footer className="bg-surface-container-lowest dark:bg-surface-container-lowest border-t border-outline-variant/30 dark:border-outline-variant mt-auto relative z-20">
          <div className="w-full py-16 px-6 md:px-10 max-w-[1300px] mx-auto">
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-8 mb-12 border-b border-outline-variant/20 pb-12">
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  <span className="material-symbols-outlined text-google-blue symbol-filled text-2xl">
                    insights
                  </span>
                  <span
                    className={`${hankenGrotesk.className} font-headline-md text-2xl font-bold text-primary dark:text-primary tracking-tight`}
                  >
                    SentiNews AI
                  </span>
                </div>
                <p className="text-on-surface-variant font-body-md text-sm max-w-sm">
                  Institutional-grade financial intelligence, powered by
                  advanced multi-agent AI architectures
                </p>
              </div>
              <div className="flex flex-wrap gap-x-8 gap-y-4">
                <div className="flex flex-col gap-2">
                  <span className="font-label-sm text-xs font-bold text-on-surface uppercase tracking-wider mb-1">
                    Product
                  </span>
                  <a
                    className="text-on-surface-variant hover:text-google-blue transition-colors text-sm"
                    href="#"
                  >
                    Research Terminal
                  </a>
                  <a
                    className="text-on-surface-variant hover:text-google-blue transition-colors text-sm"
                    href="#"
                  >
                    Market Dashboards
                  </a>
                  <a
                    className="text-on-surface-variant hover:text-google-blue transition-colors text-sm"
                    href="#"
                  >
                    API Access
                  </a>
                </div>
                <div className="flex flex-col gap-2">
                  <span className="font-label-sm text-xs font-bold text-on-surface uppercase tracking-wider mb-1">
                    Company
                  </span>
                  <a
                    className="text-on-surface-variant hover:text-google-blue transition-colors text-sm"
                    href="#"
                  >
                    About Us
                  </a>
                  <a
                    className="text-on-surface-variant hover:text-google-blue transition-colors text-sm"
                    href="#"
                  >
                    Trust Center
                  </a>
                  <a
                    className="text-on-surface-variant hover:text-google-blue transition-colors text-sm"
                    href="#"
                  >
                    Contact Sales
                  </a>
                </div>
              </div>
            </div>
            <div className="flex flex-col md:flex-row justify-between items-center gap-6">
              <p className="text-on-surface-variant/70 font-body-md text-xs text-center md:text-left max-w-3xl">
                <strong className="text-on-surface-variant">
                  Institutional Disclaimer:
                </strong>{" "}
                SentiNews AI provides algorithmic data synthesis for
                informational purposes only. It does not constitute financial
                advice, investment recommendations, or an offer to buy/sell
                securities. Past performance of AI models is not indicative of
                future market behavior. Users should verify all information with
                primary sources.
              </p>
              <div className="flex items-center gap-4 text-on-surface-variant/70 text-xs shrink-0">
                <span>© 2024 SentiNews AI</span>
                <span className="w-1 h-1 rounded-full bg-outline-variant/50"></span>
                <a className="hover:text-on-surface transition-colors" href="#">
                  Privacy
                </a>
                <span className="w-1 h-1 rounded-full bg-outline-variant/50"></span>
                <a className="hover:text-on-surface transition-colors" href="#">
                  Terms
                </a>
              </div>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}
