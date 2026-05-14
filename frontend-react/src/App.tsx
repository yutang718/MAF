import { Routes, Route } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import HomePage from './pages/HomePage'
import PromptInjectionPage from './pages/PromptInjectionPage'
import PIIDetectionPage from './pages/PIIDetectionPage'
import IslamicCompliancePage from './pages/IslamicCompliancePage'

function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/prompt-injection" element={<PromptInjectionPage />} />
        <Route path="/pii-detection" element={<PIIDetectionPage />} />
        <Route path="/islamic-compliance" element={<IslamicCompliancePage />} />
      </Routes>
    </AppLayout>
  )
}

export default App
