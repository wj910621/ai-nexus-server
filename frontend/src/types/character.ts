export interface Character {
  id: string
  user_id: string
  project_id: string | null
  name: string
  description: string | null
  style: string
  gender: string | null
  age: string | null
  hair_color: string | null
  eye_color: string | null
  skin_tone: string | null
  body_type: string | null
  lora_model_path: string | null
  lora_training_status: string
  main_image_url: string | null
  reference_images: string[]
  tags: string[]
  usage_count: number
  created_at: string
}

export interface CharacterCreate {
  name: string
  description?: string
  style?: string
  gender?: string
  age?: string
  hair_color?: string
  eye_color?: string
  skin_tone?: string
  body_type?: string
  tags?: string[]
  project_id?: string
  reference_images?: string[]
}
