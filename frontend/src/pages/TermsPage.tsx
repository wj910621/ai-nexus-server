import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import terms from '@/legal/terms.md?raw'

export default function TermsPage() {
  return <main className="min-h-screen bg-[#11111b] text-gray-100 px-6 py-10"><article className="max-w-3xl mx-auto"><ReactMarkdown remarkPlugins={[remarkGfm]}>{terms}</ReactMarkdown></article></main>
}
