import { Routes, Route } from 'react-router-dom'
import AppLayout from './components/layout/AppLayout'
import HomePage from './pages/HomePage'
import PromptInjectionPage from './pages/PromptInjectionPage'
import PIIDetectionPage from './pages/PIIDetectionPage'
import IslamicCompliancePage from './pages/IslamicCompliancePage'
import { GovAuthProvider } from './governance/auth'
import GovernanceLayout from './governance/GovernanceLayout'
import PosturePage from './governance/pages/PosturePage'
import SettingsPage from './governance/pages/SettingsPage'
import FrameworkPage from './governance/pages/FrameworkPage'
import ControlPage from './governance/pages/ControlPage'
import ChecksPage from './governance/pages/ChecksPage'
import AlertsPage from './governance/pages/AlertsPage'
import ExceptionsPage from './governance/pages/ExceptionsPage'
import ConnectorsPage from './governance/pages/ConnectorsPage'
import AdminPage from './governance/pages/AdminPage'

function App() {
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/prompt-injection" element={<PromptInjectionPage />} />
        <Route path="/pii-detection" element={<PIIDetectionPage />} />
        <Route path="/islamic-compliance" element={<IslamicCompliancePage />} />
        <Route path="/governance" element={<GovAuthProvider><GovernanceLayout /></GovAuthProvider>}>
          <Route index element={<PosturePage />} />
          <Route path="frameworks" element={<FrameworkPage />} />
          <Route path="frameworks/:fw" element={<FrameworkPage />} />
          <Route path="frameworks/:fw/controls/:cid" element={<ControlPage />} />
          <Route path="checks" element={<ChecksPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="exceptions" element={<ExceptionsPage />} />
          <Route path="connectors" element={<ConnectorsPage />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="admin" element={<AdminPage />} />
        </Route>
      </Routes>
    </AppLayout>
  )
}

export default App
