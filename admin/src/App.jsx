import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Layout from './components/Layout'
import PrivateRoute from './components/PrivateRoute'
import Login from './pages/Login'
import Efetivo from './pages/Efetivo'
import Utilizadores from './pages/Utilizadores'
import { Loading } from './components/ui'
import { lazy, Suspense } from 'react'

const Dashboard   = lazy(() => import('./pages/Dashboard'))
const EscalaGeral = lazy(() => import('./pages/EscalaGeral'))
const GerarEscala = lazy(() => import('./pages/GerarEscala'))
const Publicar    = lazy(() => import('./pages/Publicar'))
const Ferias      = lazy(() => import('./pages/Ferias'))
const Dispensas   = lazy(() => import('./pages/Dispensas'))
const Remunerados = lazy(() => import('./pages/Remunerados'))
const Alertas     = lazy(() => import('./pages/Alertas'))
const Giros       = lazy(() => import('./pages/Giros'))

const qc = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
})

function AdminRoutes() {
  return (
    <PrivateRoute>
      <Layout />
    </PrivateRoute>
  )
}

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter basename="/admin">
        <Suspense fallback={<div className="flex items-center justify-center h-screen"><Loading /></div>}>
          <Routes>
            <Route path="/" element={<Login />} />
            <Route element={<AdminRoutes />}>
              <Route path="/dashboard"    element={<Dashboard />} />
              <Route path="/escala-geral" element={<EscalaGeral />} />
              <Route path="/gerar-escala" element={<GerarEscala />} />
              <Route path="/publicar"     element={<Publicar />} />
              <Route path="/ferias"       element={<Ferias />} />
              <Route path="/dispensas"    element={<Dispensas />} />
              <Route path="/remunerados"  element={<Remunerados />} />
              <Route path="/alertas"      element={<Alertas />} />
              <Route path="/giros"        element={<Giros />} />
              <Route path="/efetivo"      element={<Efetivo />} />
              <Route path="/utilizadores" element={<Utilizadores />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
