import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "./api";
import type { AppConfig, User } from "./types";

/** Which sign-in methods this deployment offers. Fetched at runtime, so one
 *  built image works in every environment. */
export function useConfig() {
  return useQuery<AppConfig>({
    queryKey: ["config"],
    queryFn: api.config,
    staleTime: Infinity,
  });
}

/** Current user, or null when signed out. A 401 is an answer, not an error. */
export function useMe() {
  return useQuery<User | null>({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await api.me();
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) return null;
        throw err;
      }
    },
    staleTime: 5 * 60 * 1000,
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: api.logout,
    onSuccess: () => {
      qc.setQueryData(["me"], null);
      qc.clear(); // don't leak the previous user's lists into the next session
    },
  });
}
