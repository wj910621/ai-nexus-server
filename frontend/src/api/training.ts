import type { AxiosResponse } from 'axios'
import { apiClient } from './client'
import type { ApiResponse } from '@/types'
import type {
  TrainRequest,
  TrainResponse,
  TrainStatus,
} from '@/types/training'
import type { Dataset, DatasetCreate, DatasetItem } from '@/types/dataset'

/** 提交训练任务 */
export async function submitTrain(
  characterId: string,
  data: TrainRequest,
): Promise<AxiosResponse<ApiResponse<TrainResponse>>> {
  return apiClient.post<ApiResponse<TrainResponse>>(
    `/characters/${characterId}/train`,
    data,
  )
}

/** 查询训练状态 */
export async function getTrainStatus(
  characterId: string,
): Promise<AxiosResponse<ApiResponse<TrainStatus>>> {
  return apiClient.get<ApiResponse<TrainStatus>>(
    `/characters/${characterId}/train/status`,
  )
}

/** 创建数据集 */
export async function createDataset(
  data: DatasetCreate,
): Promise<AxiosResponse<ApiResponse<Dataset>>> {
  return apiClient.post<ApiResponse<Dataset>>('/datasets', data)
}

/** 获取数据集详情 */
export async function getDataset(
  datasetId: string,
): Promise<AxiosResponse<ApiResponse<Dataset>>> {
  return apiClient.get<ApiResponse<Dataset>>(`/datasets/${datasetId}`)
}

/** 上传图片到数据集 */
export async function uploadImage(
  datasetId: string,
  file: File,
): Promise<AxiosResponse<ApiResponse<DatasetItem>>> {
  const formData = new FormData()
  formData.append('file', file)
  return apiClient.post<ApiResponse<DatasetItem>>(
    `/datasets/${datasetId}/images`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
    },
  )
}

/** 更新单张图片 caption */
export async function updateCaption(
  datasetId: string,
  itemId: string,
  caption: string,
): Promise<AxiosResponse<ApiResponse<DatasetItem>>> {
  return apiClient.post<ApiResponse<DatasetItem>>(
    `/datasets/${datasetId}/images/${itemId}/caption`,
    {
      caption,
    },
  )
}

/** 批量自动生成 caption */
export async function autoCaption(
  datasetId: string,
): Promise<AxiosResponse<ApiResponse<{ count: number }>>> {
  return apiClient.post<ApiResponse<{ count: number }>>(
    `/datasets/${datasetId}/auto-caption`,
  )
}

/** 删除数据集图片 */
export async function deleteImage(
  datasetId: string,
  itemId: string,
): Promise<AxiosResponse<ApiResponse<{ deleted: string }>>> {
  return apiClient.delete<ApiResponse<{ deleted: string }>>(
    `/datasets/${datasetId}/images/${itemId}`,
  )
}

/** 获取角色数据集列表 */
export async function listCharacterDatasets(
  characterId: string,
): Promise<AxiosResponse<ApiResponse<Dataset[]>>> {
  return apiClient.get<ApiResponse<Dataset[]>>(
    `/characters/${characterId}/datasets`,
  )
}
