'use client'

import { useState, useRef, useEffect, useCallback } from 'react'
import { ChevronLeft, ChevronRight, Calendar } from 'lucide-react'

const JOURS = ['Lu', 'Ma', 'Me', 'Je', 'Ve', 'Sa', 'Di']
const MOIS = [
  'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
  'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre',
]

function getDaysInMonth(year: number, month: number) {
  return new Date(year, month + 1, 0).getDate()
}

function getFirstDayOfWeek(year: number, month: number) {
  const day = new Date(year, month, 1).getDay()
  return day === 0 ? 6 : day - 1 // Monday = 0
}

function formatDisplayDate(dateStr: string) {
  if (!dateStr) return ''
  const [y, m, d] = dateStr.split('-').map(Number)
  return `${d} ${MOIS[m - 1]} ${y}`
}

function toDateStr(y: number, m: number, d: number) {
  return `${y}-${String(m + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

interface DatePickerProps {
  value: string
  onChange: (value: string) => void
  placeholder?: string
}

export default function DatePicker({ value, onChange, placeholder = 'Sélectionner une date' }: DatePickerProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const today = new Date()
  const initialDate = value ? new Date(value) : today
  const [viewYear, setViewYear] = useState(initialDate.getFullYear())
  const [viewMonth, setViewMonth] = useState(initialDate.getMonth())

  const selectedDay = value ? Number(value.split('-')[2]) : null
  const selectedMonth = value ? Number(value.split('-')[1]) - 1 : null
  const selectedYear = value ? Number(value.split('-')[0]) : null

  const daysInMonth = getDaysInMonth(viewYear, viewMonth)
  const firstDay = getFirstDayOfWeek(viewYear, viewMonth)

  const prevMonth = useCallback(() => {
    if (viewMonth === 0) {
      setViewMonth(11)
      setViewYear(y => y - 1)
    } else {
      setViewMonth(m => m - 1)
    }
  }, [viewMonth])

  const nextMonth = useCallback(() => {
    if (viewMonth === 11) {
      setViewMonth(0)
      setViewYear(y => y + 1)
    } else {
      setViewMonth(m => m + 1)
    }
  }, [viewMonth])

  function selectDay(day: number) {
    onChange(toDateStr(viewYear, viewMonth, day))
    setOpen(false)
  }

  function clearDate(e: React.MouseEvent) {
    e.stopPropagation()
    onChange('')
    setOpen(false)
  }

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  useEffect(() => {
    if (open && value) {
      const d = new Date(value)
      setViewYear(d.getFullYear())
      setViewMonth(d.getMonth())
    }
  }, [open, value])

  const isToday = (day: number) =>
    viewYear === today.getFullYear() && viewMonth === today.getMonth() && day === today.getDate()

  const isSelected = (day: number) =>
    viewYear === selectedYear && viewMonth === selectedMonth && day === selectedDay

  return (
    <div className="relative" ref={ref}>
      {/* Trigger */}
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className={`w-full border bg-white px-3.5 py-2.5 flex items-center gap-3 transition-all duration-200 rounded-lg text-left ${
          open
            ? 'border-neutral-900 ring-1 ring-neutral-900'
            : 'border-neutral-300 hover:border-neutral-400'
        }`}
      >
        <Calendar className="w-4 h-4 text-neutral-400 shrink-0" />
        <span className={`flex-1 text-sm font-medium ${value ? 'text-neutral-900' : 'text-neutral-400'}`}>
          {value ? formatDisplayDate(value) : placeholder}
        </span>
        {value && (
          <span
            onClick={clearDate}
            className="text-neutral-400 hover:text-neutral-600 transition-colors cursor-pointer text-xs font-medium"
          >
            ✕
          </span>
        )}
      </button>

      {/* Dropdown calendar */}
      {open && (
        <div className="absolute top-full left-0 mt-2 z-50 bg-white border border-neutral-200 rounded-xl shadow-lg shadow-neutral-900/8 p-4 w-[300px] animate-in fade-in slide-in-from-top-1 duration-150">
          {/* Header */}
          <div className="flex items-center justify-between mb-4">
            <button
              type="button"
              onClick={prevMonth}
              className="w-8 h-8 rounded-lg flex items-center justify-center text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 transition-all duration-150"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="text-sm font-semibold text-neutral-900 tracking-tight">
              {MOIS[viewMonth]} {viewYear}
            </span>
            <button
              type="button"
              onClick={nextMonth}
              className="w-8 h-8 rounded-lg flex items-center justify-center text-neutral-500 hover:bg-neutral-100 hover:text-neutral-900 transition-all duration-150"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          {/* Day headers */}
          <div className="grid grid-cols-7 mb-1">
            {JOURS.map(j => (
              <div key={j} className="text-center text-[11px] font-semibold text-neutral-400 uppercase tracking-wide py-1.5">
                {j}
              </div>
            ))}
          </div>

          {/* Day grid */}
          <div className="grid grid-cols-7">
            {Array.from({ length: firstDay }).map((_, i) => (
              <div key={`empty-${i}`} />
            ))}
            {Array.from({ length: daysInMonth }, (_, i) => i + 1).map(day => {
              const selected = isSelected(day)
              const todayMark = isToday(day)
              return (
                <button
                  key={day}
                  type="button"
                  onClick={() => selectDay(day)}
                  className={`h-9 w-full rounded-lg text-[13px] font-medium transition-all duration-150 relative
                    ${selected
                      ? 'bg-neutral-900 text-white shadow-sm'
                      : todayMark
                        ? 'text-brand-600 font-semibold hover:bg-brand-50'
                        : 'text-neutral-700 hover:bg-neutral-100'
                    }`}
                >
                  {day}
                  {todayMark && !selected && (
                    <span className="absolute bottom-1 left-1/2 -translate-x-1/2 w-1 h-1 rounded-full bg-brand-500" />
                  )}
                </button>
              )
            })}
          </div>

          {/* Footer */}
          <div className="mt-3 pt-3 border-t border-neutral-100 flex items-center justify-between">
            <button
              type="button"
              onClick={() => {
                onChange(toDateStr(today.getFullYear(), today.getMonth(), today.getDate()))
                setOpen(false)
              }}
              className="text-[12px] font-semibold text-brand-600 hover:text-brand-700 transition-colors"
            >
              Aujourd&apos;hui
            </button>
            {value && (
              <button
                type="button"
                onClick={(e) => clearDate(e)}
                className="text-[12px] font-medium text-neutral-400 hover:text-neutral-600 transition-colors"
              >
                Effacer
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
