import { Navigate } from 'react-router-dom'
import { useAuth } from '../store/auth'

export default function PrivateRoute({ children }) {
  const { token, user } = useAuth()
  if (!token || !user?.is_admin) return <Navigate to="/" replace />
  return children
}
