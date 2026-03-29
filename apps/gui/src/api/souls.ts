import { api } from "./client";
import {
  SoulResponse,
  SoulResponseSchema,
  SoulListResponse,
  SoulListResponseSchema,
  SoulCreate,
  SoulUpdate,
} from "@runsight/shared/zod";

export const soulsApi = {
  listSouls: async (): Promise<SoulListResponse> => {
    const res = await api.get(`/souls`);
    return SoulListResponseSchema.parse(res);
  },

  getSoul: async (id: string): Promise<SoulResponse> => {
    const res = await api.get(`/souls/${id}`);
    return SoulResponseSchema.parse(res);
  },

  createSoul: async (data: SoulCreate): Promise<SoulResponse> => {
    const res = await api.post(`/souls`, data);
    return SoulResponseSchema.parse(res);
  },

  updateSoul: async (id: string, data: SoulUpdate): Promise<SoulResponse> => {
    const res = await api.put(`/souls/${id}`, data);
    return SoulResponseSchema.parse(res);
  },

  deleteSoul: async (id: string): Promise<{ id: string; deleted: boolean }> => {
    const res = await api.delete<{ id: string; deleted: boolean }>(`/souls/${id}`);
    return res;
  },
};
