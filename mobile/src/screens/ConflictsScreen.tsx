import React, { useCallback, useEffect, useState } from "react";
import { View, Text, FlatList, ActivityIndicator, StyleSheet, RefreshControl } from "react-native";

import { ApiClient, ConflictRecord } from "../api/apiClient";
import { colors } from "../theme/colors";

/** Shows every unresolved conflict for this tenant, fetched fresh
 * from the server (GET /v1/mfa/conflicts) -- deliberately not read
 * from the local cache alone, since a conflict is exactly the kind
 * of thing where a stale local view is actively unhelpful.
 *
 * Real, honest limitation: this screen displays conflicts and lets a
 * user see both sides (their own captured data vs. what the server
 * actually has), but does not yet call
 * POST /v1/mfa/conflicts/<id>/resolve -- that write action needs a
 * real UI for constructing a resolution payload matching what each
 * conflict_type actually needs, which is real, separate follow-up
 * work, not attempted here. Today, resolving a conflict means going
 * to the web app. */
interface Props {
  apiClient: ApiClient;
}

export default function ConflictsScreen({ apiClient }: Props) {
  const [conflicts, setConflicts] = useState<ConflictRecord[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setErrorMessage(null);
    try {
      const result = await apiClient.getConflicts();
      setConflicts(result.filter((c) => c.status === "unresolved"));
    } catch {
      setErrorMessage("Could not load conflicts. Check your connection.");
    } finally {
      setIsLoading(false);
    }
  }, [apiClient]);

  useEffect(() => {
    load();
  }, [load]);

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator />
      </View>
    );
  }

  if (errorMessage) {
    return (
      <View style={styles.centered}>
        <Text>{errorMessage}</Text>
      </View>
    );
  }

  return (
    <FlatList
      style={styles.container}
      contentContainerStyle={styles.content}
      data={conflicts}
      keyExtractor={(item) => item.id}
      refreshControl={<RefreshControl refreshing={isLoading} onRefresh={load} />}
      ListEmptyComponent={
        <View style={styles.centered}>
          <Text>No unresolved conflicts.</Text>
        </View>
      }
      renderItem={({ item }) => <ConflictCard conflict={item} />}
    />
  );
}

function ConflictCard({ conflict }: { conflict: ConflictRecord }) {
  return (
    <View style={styles.card}>
      <View style={styles.badge}>
        <Text style={styles.badgeText}>{conflict.conflict_type.replace(/_/g, " ")}</Text>
      </View>

      <Text style={styles.sectionTitle}>What you captured:</Text>
      <Text style={styles.json}>{JSON.stringify(conflict.client_payload, null, 2)}</Text>

      {conflict.server_current_state && (
        <>
          <Text style={styles.sectionTitle}>What the server has:</Text>
          <Text style={styles.json}>{JSON.stringify(conflict.server_current_state, null, 2)}</Text>
        </>
      )}

      <Text style={styles.italicNote}>
        Resolving this isn't available in the app yet — please use the web app to decide what happens next.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.paper },
  content: { padding: 16 },
  centered: { flex: 1, alignItems: "center", justifyContent: "center", padding: 32 },
  card: { backgroundColor: colors.white, borderRadius: 3, borderWidth: 1, borderColor: colors.line, padding: 16, marginBottom: 12 },
  badge: { alignSelf: "flex-start", backgroundColor: colors.brickDim, borderRadius: 3, paddingHorizontal: 8, paddingVertical: 4 },
  badgeText: { color: colors.brick, fontWeight: "600", fontSize: 12 },
  sectionTitle: { marginTop: 12, fontWeight: "600" },
  json: { fontFamily: "monospace", fontSize: 12 },
  italicNote: { marginTop: 12, color: colors.navy600, fontStyle: "italic" },
});
