export interface Dataset {
  id: string
  character_id: string
  user_id: string
  name: string
  status: 'drafting' | 'captioning' | 'ready' | 'training' | 'used'
  image_count: number
  caption_mode: 'auto' | 'manual'
  trigger_word: string
  created_at: string
  updated_at?: string
  items: DatasetItem[]
}

export interface DatasetItem {
  id: string
  dataset_id: string
  image_path: string
  caption: string
  caption_source: 'auto' | 'manual' | 'imported'
  width: number | null
  height: number | null
  created_at: string
}

export interface DatasetCreate {
  character_id: string
  name: string
  caption_mode: 'auto' | 'manual'
  trigger_word: string
}
