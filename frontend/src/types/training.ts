export type TrainLocation = 'local' | 'replicate'
export type TrainPreset = 'quick' | 'standard' | 'high_quality'

export interface TrainParamsAdvanced {
  rank?: number
  learning_rate?: number
  max_train_steps?: number
  batch_size?: number
  gradient_accumulation?: number
}

export interface TrainRequest {
  dataset_id: string
  location: TrainLocation
  trigger_word: string
  preset: TrainPreset
  advanced?: TrainParamsAdvanced
}

export interface TrainResponse {
  task_id: string
  character_id: string
  status: string
}

export interface TrainStatus {
  status: string
  progress: number
  message: string
  task_id: string | null
}
