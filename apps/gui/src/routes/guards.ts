import { redirect } from "react-router";
import type { QueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/queries/keys";
import { settingsApi } from "@/api/settings";

export function createSetupGuardLoader(queryClient: QueryClient) {
  return async () => {
    try {
      const settings = await queryClient.fetchQuery({
        queryKey: queryKeys.settings.appSettings,
        queryFn: settingsApi.getAppSettings,
        staleTime: 30_000,
      });

      if (!settings.onboarding_completed) {
        throw redirect("/setup/start");
      }

      return null;
    } catch (error) {
      if (error instanceof Response) throw error;
      return null;
    }
  };
}

export function createReverseGuardLoader(queryClient: QueryClient) {
  return async () => {
    try {
      const settings = await queryClient.fetchQuery({
        queryKey: queryKeys.settings.appSettings,
        queryFn: settingsApi.getAppSettings,
        staleTime: 30_000,
      });

      if (settings.onboarding_completed === true) {
        throw redirect("/");
      }

      return null;
    } catch (error) {
      if (error instanceof Response) throw error;
      return null;
    }
  };
}
