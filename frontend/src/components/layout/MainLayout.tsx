import { Outlet, useNavigate } from 'react-router-dom'
import Sidebar from './Sidebar'
import TopBar from './TopBar'
import AiDock from './AiDock'
import CommandBar from './CommandBar'
import { useAgentStore } from '@/stores/agentStore'

export default function MainLayout() {
  const navigate = useNavigate()
  const handleCommand = (text: string) => {
    useAgentStore.getState().setDraft(text)
    const { pathname } = window.location
    if (!pathname.startsWith('/agent')) navigate('/agent')
  }
  return (
    <div className="flex h-screen bg-[#1e1e2e] text-white">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-auto bg-[#181825]">
          <Outlet />
        </main>
        <CommandBar onSend={handleCommand} />
      </div>
      <AiDock />
    </div>
  )
}
