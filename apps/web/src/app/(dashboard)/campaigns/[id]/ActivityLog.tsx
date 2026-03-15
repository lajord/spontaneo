'use client'

import { useEffect, useRef } from 'react'

export type ActivityEvent = {
  id: string
  timestamp: Date
  type: 'info' | 'progress' | 'success' | 'error'
  message: string
  detail?: string
}

interface ActivityLogProps {
  events: ActivityEvent[]
}

function formatTime(date: Date) {
  return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const dotStyles: Record<ActivityEvent['type'], string> = {
  info: 'bg-slate-400',
  progress: 'bg-brand-500 animate-pulse',
  success: 'bg-emerald-500',
  error: 'bg-red-500',
}

const textStyles: Record<ActivityEvent['type'], string> = {
  info: 'text-slate-600',
  progress: 'text-slate-700',
  success: 'text-emerald-700',
  error: 'text-red-600',
}

export default function ActivityLog({ events }: ActivityLogProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events.length])

  return (
    <div className="border border-slate-300 rounded-2xl bg-white h-full flex flex-col">
      {/* Header */}
      <div className="px-5 py-4 border-b border-slate-300 flex items-center gap-2.5 shrink-0">
        <div className="w-2 h-2 rounded-full bg-slate-300" />
        <h3 className="text-sm font-semibold text-slate-700">Journal d&apos;activité</h3>
      </div>

      {/* Events */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-3">
        {events.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-slate-600 font-mono">En attente du lancement...</p>
          </div>
        ) : (
          <div className="space-y-3">
            {events.map((event) => (
              <div key={event.id} className="flex items-start gap-3">
                <span className="text-[10px] font-mono text-slate-600 mt-0.5 shrink-0 w-14">
                  {formatTime(event.timestamp)}
                </span>
                <div className={`w-1.5 h-1.5 rounded-full mt-1.5 shrink-0 ${dotStyles[event.type]}`} />
                <div className="min-w-0 flex-1">
                  <p className={`text-[13px] font-medium leading-snug ${textStyles[event.type]}`}>
                    {event.message}
                  </p>
                  {event.detail && (
                    <p className="text-[11px] text-slate-600 mt-0.5">{event.detail}</p>
                  )}
                </div>
              </div>
            ))}
            <div ref={endRef} />
          </div>
        )}
      </div>
    </div>
  )
}
