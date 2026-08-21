export interface Project {
  id: string
  user_id: string
  name: string
  description: string | null
  genre: string | null
  status: string
  config: {
    resolution?: string
    fps?: number
    style?: string
  }
  character_count: number
  scene_count: number
  frame_count: number
  is_shared: boolean
  collaborators: unknown[]
  created_at: string
  updated_at: string
}

export interface ProjectCreate {
  name: string
  description?: string
  genre?: string
  config?: Partial<Project['config']>
}

export interface ProjectUpdate {
  name?: string
  description?: string
  genre?: string
  status?: string
  config?: Partial<Project['config']>
}
