import { api } from "./client";
import type { components } from "@runsight/shared/api";
import {
  SoulListResponseSchema,
  SoulResponseSchema,
  SoulUsageResponseSchema,
  ToolListItemResponseSchema,
} from "@runsight/shared/zod";
import type {
  SoulCreate,
  SoulListResponse,
  SoulResponse,
  SoulUpdate,
  SoulUsageResponse,
} from "@runsight/shared/zod";
import { z } from "zod";

type ToolListItemResponse = components["schemas"]["ToolListItemResponse"];

const AvailableToolListSchema = z.array(ToolListItemResponseSchema);

export const soulsApi = {
  listSouls: async (): Promise<SoulListResponse> => {
    const res = await api.get(`/souls`);
    return SoulListResponseSchema.parse(res);
  },

  getSoul: async (id: string): Promise<SoulResponse> => {
    const res = await api.get(`/souls/${id}`);
    return SoulResponseSchema.parse(res);
  },

  getSoulUsages: async (id: string): Promise<SoulUsageResponse> => {
    const res = await api.get(`/souls/${id}/usages`);
    return SoulUsageResponseSchema.parse(res);
  },

  listAvailableTools: async (): Promise<ToolListItemResponse[]> => {
    const res = await api.get(`/tools`);
    return AvailableToolListSchema.parse(res) as ToolListItemResponse[];
  },

  createSoul: async (data: SoulCreate): Promise<SoulResponse> => {
    const res = await api.post(`/souls`, data);
    return SoulResponseSchema.parse(res);
  },

  updateSoul: async (id: string, data: SoulUpdate): Promise<SoulResponse> => {
    const res = await api.put(`/souls/${id}`, data);
    return SoulResponseSchema.parse(res);
  },

  deleteSoul: async (
    id: string,
    force = false,
  ): Promise<{ id: string; deleted: boolean }> => {
    const query = force ? "?force=true" : "";
    const res = await api.delete<{ id: string; deleted: boolean }>(`/souls/${id}${query}`);
    return res;
  },
};
