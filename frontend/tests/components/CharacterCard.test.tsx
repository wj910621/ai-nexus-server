import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import CharacterCard from '@/components/characters/CharacterCard'
import type { Character } from '@/types/character'

const baseCharacter: Character = {
  id: 'ch_1',
  user_id: 'u_1',
  project_id: 'p_1',
  name: '测试角色',
  description: '',
  style: 'realistic',
  gender: null,
  age: null,
  hair_color: null,
  eye_color: null,
  skin_tone: null,
  body_type: null,
  lora_model_path: '',
  lora_training_status: 'none',
  main_image_url: '',
  reference_images: [],
  tags: [],
  usage_count: 0,
  created_at: '',
}

function renderCard(overrides: Partial<Character> = {}) {
  return render(
    <MemoryRouter>
      <CharacterCard character={{ ...baseCharacter, ...overrides }} />
    </MemoryRouter>,
  )
}

describe('CharacterCard LoRA 徽章', () => {
  it('lora_training_status=none 显示"未训练"', () => {
    renderCard({ lora_training_status: 'none' })
    expect(screen.getByText('未训练')).toBeInTheDocument()
  })

  it('lora_training_status=training 显示"训练中"（带链接）', () => {
    renderCard({ lora_training_status: 'training' })
    expect(screen.getByText('训练中')).toBeInTheDocument()
    expect(screen.getByText('训练中').closest('a')).toHaveAttribute(
      'href',
      '/characters/ch_1/train',
    )
  })

  it('lora_training_status=ready 显示"已训练"', () => {
    renderCard({ lora_training_status: 'ready' })
    expect(screen.getByText('已训练')).toBeInTheDocument()
  })

  it('lora_training_status=failed 显示"训练失败"', () => {
    renderCard({ lora_training_status: 'failed' })
    expect(screen.getByText('训练失败')).toBeInTheDocument()
  })

  it('包含"训练 LoRA"按钮（无 LoRA 时）', () => {
    renderCard({ lora_training_status: 'none' })
    expect(screen.getByText('训练 LoRA')).toBeInTheDocument()
  })

  it('ready 状态显示"用此角色生图"按钮', () => {
    renderCard({ lora_training_status: 'ready' })
    // 默认未开启商业化运营，按钮带"（暂未开放）"后缀且处于禁用态，
    // 与 CharacterCard 中商业运营开关对应的 UI 保持一致。
    expect(screen.getByText('用此角色生图（暂未开放）')).toBeInTheDocument()
    const btn = screen.getByRole('button', { name: '用此角色生图（暂未开放）' })
    expect(btn).toBeDisabled()
  })
})
