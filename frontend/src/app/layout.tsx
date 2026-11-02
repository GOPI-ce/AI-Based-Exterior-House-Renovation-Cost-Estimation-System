import type { Metadata, Viewport } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";

import { Toaster } from "@/components/Toaster";

import "./globals.css";

const jakarta = Plus_Jakarta_Sans({ variable: "--font-jakarta", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "FacadeAI · Exterior renovation planner",
  description:
    "Upload a photo of your house, let AI map its walls, pillars, balconies and gates, try materials on your own home and get a transparent quantity and cost estimate.",
};

export const viewport: Viewport = {
  themeColor: "#1f5f45",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${jakarta.variable} h-full`}>
      <body className="min-h-full font-sans antialiased">
        {children}
        <Toaster />
      </body>
    </html>
  );
}
