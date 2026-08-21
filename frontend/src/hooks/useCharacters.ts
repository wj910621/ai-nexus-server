import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { characterApi } from '@/api/characters'
import type { CharacterCreate } from '@/types'

export function useCharacters(projectId?: string) {
  return useQuery({
    queryKey: ['characters', projectId],
    queryFn: async () => {
      const res = await characterApi.list(projectId)
      return res.data.data
    },
    enabled: true,
  })
}

export function useCreateCharacter() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (data: CharacterCreate) => {
      const res = await characterApi.create(data)
      return res.data.data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['characters'] })
    },
  })
}
