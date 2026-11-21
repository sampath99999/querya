import { useCallback, useEffect, useState } from 'react'
import { AskView } from './components/AskView'
import { HistoryView } from './components/HistoryView'
import { Sidebar, type View } from './components/Sidebar'
import { useAsk } from './hooks/useAsk'

interface Route {
  view: View
  runId: string | null
}

function parseHash(): Route {
  const [, view, runId] = window.location.hash.replace(/^#/, '').split('/')
  if (view === 'history') return { view: 'history', runId: runId ? decodeURIComponent(runId) : null }
  return { view: 'ask', runId: null }
}

function navigate(route: Route): void {
  const hash = route.view === 'history' ? `#/history${route.runId ? `/${encodeURIComponent(route.runId)}` : ''}` : '#/'
  if (window.location.hash !== hash) window.location.hash = hash
}

export default function App() {
  const [route, setRoute] = useState<Route>(parseHash)
  const [historyKey, setHistoryKey] = useState(0)
  const bumpHistory = useCallback(() => setHistoryKey((k) => k + 1), [])
  const askState = useAsk(bumpHistory)

  useEffect(() => {
    const onHash = () => setRoute(parseHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  return (
    <div className="flex h-dvh flex-col md:flex-row">
      <Sidebar
        view={route.view}
        onNavigate={(view) => navigate({ view, runId: null })}
        onNewChat={() => {
          askState.reset()
          navigate({ view: 'ask', runId: null })
        }}
      />
      <main className="scrollbar-thin min-h-0 min-w-0 flex-1 overflow-y-auto">
        {route.view === 'ask' ? (
          <AskView state={askState} />
        ) : (
          <HistoryView
            selectedId={route.runId}
            onSelect={(runId) => navigate({ view: 'history', runId })}
            refreshKey={historyKey}
          />
        )}
      </main>
    </div>
  )
}
