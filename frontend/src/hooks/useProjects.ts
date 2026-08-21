import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { projectApi } from '@/api/projects'
import type { ProjectCreate } from '@/types'

export function useProjects(page = 1, pageSize = 20) {
  return useQuery({
    queryKey: ['projects', page, pageSize],
    queryFn: async () => {
      const res = await projectApi.list(page, pageSize)
      return res.data.data
    },
  })
}

export function useCreateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: ProjectCreate) => {
      const res = await projectApi.create(data)
      return res.data.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}

export function useDeleteProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await projectApi.delete(id)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] })
    },
  })
}
