import { redirect } from "react-router";
import type { QueryClient } from "@tanstack/react-query";
import { queryKeys } from "@/queries/keys";
import { settingsApi } from "@/api/settings";

function readOnboardingCompleted(settings: { onboarding_completed?: unknown }) {
  if (typeof settings.onboarding_completed !== "boolean") {
    throw new Error("Invalid app settings payload");
  }

  return settings.onboarding_completed;
}

function withGuardRetryLocation(unavailableRedirect: Response, request: Request) {
  const url = new URL(request.url);
  const retryTo = `${url.pathname}${url.search}`;
  const location = unavailableRedirect.headers.get("Location");

  if (!location) {
    return unavailableRedirect;
  }

  const unavailableUrl = new URL(location, request.url);
  unavailableUrl.searchParams.set("retryTo", retryTo);
  unavailableRedirect.headers.set(
    "Location",
    `${unavailableUrl.pathname}${unavailableUrl.search}`,
  );

  return unavailableRedirect;
}

export function createSetupGuardLoader(queryClient: QueryClient) {
  return async ({ request }: { request: Request }) => {
    try {
      const settings = await queryClient.fetchQuery({
        queryKey: queryKeys.settings.appSettings,
        queryFn: settingsApi.getAppSettings,
        staleTime: 0,
      });
      readOnboardingCompleted(settings);

      if (settings.onboarding_completed === false) {
        throw redirect("/setup/start");
      }

      return null;
    } catch (error) {
      if (error instanceof Response) throw error;
      const unavailableRedirect = redirect("/setup/unavailable");
      throw withGuardRetryLocation(unavailableRedirect, request);
    }
  };
}

export function createReverseGuardLoader(queryClient: QueryClient) {
  return async ({ request }: { request: Request }) => {
    try {
      const settings = await queryClient.fetchQuery({
        queryKey: queryKeys.settings.appSettings,
        queryFn: settingsApi.getAppSettings,
        staleTime: 0,
      });
      const onboardingCompleted = readOnboardingCompleted(settings);

      if (onboardingCompleted === true) {
        throw redirect("/");
      }

      return null;
    } catch (error) {
      if (error instanceof Response) throw error;
      const unavailableRedirect = redirect("/setup/unavailable");
      throw withGuardRetryLocation(unavailableRedirect, request);
    }
  };
}
