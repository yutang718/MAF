import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { I18nProvider } from './i18n/context'
import { ThemeProvider } from './theme/context'
import { HealthProvider } from './health/HealthProvider'
import App from './App'
import './index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <I18nProvider>
        <HealthProvider>
          <BrowserRouter>
            <App />
          </BrowserRouter>
        </HealthProvider>
      </I18nProvider>
    </ThemeProvider>
  </StrictMode>,
)
