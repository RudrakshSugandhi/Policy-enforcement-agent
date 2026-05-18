'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { LayoutDashboard, ShieldCheck, FlaskConical } from 'lucide-react'

const links = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/policy/create', label: 'Policy', icon: ShieldCheck },
  { href: '/evaluate', label: 'Evaluate', icon: FlaskConical },
]

export function Sidebar() {
  const path = usePathname()
  return (
    <aside className="w-56 flex-shrink-0 flex flex-col bg-brand-teal text-brand-light">
      <div className="px-5 py-5 border-b border-brand-teal-dark">
        <span className="font-semibold text-base tracking-tight">Reap Policy Agent</span>
      </div>
      <nav className="flex-1 py-4 space-y-1 px-3">
        {links.map(({ href, label, icon: Icon }) => {
          const active = href === '/' ? path === '/' : path.startsWith(href)
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                active
                  ? 'bg-brand-teal-dark text-white'
                  : 'text-brand-light hover:bg-brand-teal-dark/60'
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          )
        })}
      </nav>
      <div className="px-5 py-4 border-t border-brand-teal-dark text-xs text-brand-light/60">
        Tenant: {process.env.NEXT_PUBLIC_TENANT_ID ?? 'meru-inc'}
      </div>
    </aside>
  )
}
