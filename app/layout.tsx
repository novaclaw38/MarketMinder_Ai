import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'MarketMinder AI',
  description: 'AI-powered competitive intelligence & market research platform',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-gray-50 text-gray-900">
        {children}
      </body>
    </html>
  )
}