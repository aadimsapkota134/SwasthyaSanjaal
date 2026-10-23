import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { NavHeader } from "@/components/nav-header";
import { AuthProvider } from "@/lib/auth-context";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Swasthya Sanjaal",
  description: "Nepali Clinical Language Layer — structured, reviewable clinical records",
};

export default function RootLayout({
  children,
}: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <AuthProvider>
          <NavHeader />
          <div className="shell">
            <main className="main">{children}</main>
          </div>
        </AuthProvider>
      </body>
    </html>
  );
}
