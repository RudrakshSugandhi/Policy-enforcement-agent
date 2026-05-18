import type { Metadata } from 'next'
import './globals.css'
import { Sidebar } from '@/components/layout/Sidebar'
import { TopBar } from '@/components/layout/TopBar'

export const metadata: Metadata = {
  title: 'Reap Policy Agent',
  description: 'Policy enforcement agent for spend management',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="flex h-screen overflow-hidden">
        <Sidebar />
        <div className="flex flex-col flex-1 overflow-hidden">
          <TopBar />
          <main className="flex-1 overflow-y-auto p-6 bg-muted-bg">
            {children}
          </main>
        </div>
      </body>
    </html>
  )
}
