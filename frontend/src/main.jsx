import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import 'leaflet/dist/leaflet.css'
import './styles.css'
import App from './App'

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchIntervalInBackground: false } } })
ReactDOM.createRoot(document.getElementById('root')).render(
  <QueryClientProvider client={qc}><BrowserRouter><App /></BrowserRouter></QueryClientProvider>
)
