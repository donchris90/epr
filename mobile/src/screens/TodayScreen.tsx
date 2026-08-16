import React, { useCallback, useEffect, useState } from "react";
import { View, Text, TextInput, Pressable, StyleSheet, ActivityIndicator } from "react-native";
import * as SQLite from "expo-sqlite";
import * as SecureStore from "expo-secure-store";
import { useFocusEffect } from "@react-navigation/native";

import { ApiClient } from "../api/apiClient";
import { SyncService } from "../sync/syncService";
import { getDiaryForProjectAndDate, countPendingSyncEntries, countUnresolvedConflicts, LocalDiary } from "../db/database";
import { colors } from "../theme/colors";
import type { TodayScreenProps } from "../navigation/types";

const PROJECT_ID_KEY = "sf_current_project_id";

/** "Today" screen -- the mobile home (SRS 7.2.2, Daily Site Diary
 * Flow). Shows the current project's diary status and a persistent
 * offline/sync-status indicator (SRS 7.3 design note).
 *
 * Real, honest limitation: project selection here is a plain manual
 * entry, not a picker backed by a verified "my assigned projects"
 * endpoint -- no such endpoint was found and confirmed in the real
 * backend during this pass. A field user types their project ID
 * once; it's remembered locally after that. Replacing this with a
 * real assignment-aware picker is real, separate follow-up work. */
interface Props extends TodayScreenProps {
  db: SQLite.SQLiteDatabase;
  apiClient: ApiClient;
  syncService: SyncService;
}

export default function TodayScreen({ db, apiClient, syncService, navigation }: Props) {
  const [projectId, setProjectId] = useState<string | null>(null);
  const [projectInput, setProjectInput] = useState("");
  const [todayDiary, setTodayDiary] = useState<LocalDiary | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [conflictCount, setConflictCount] = useState(0);
  const [isOnline, setIsOnline] = useState(true);
  const [isLoading, setIsLoading] = useState(true);
  const [isSyncing, setIsSyncing] = useState(false);

  const todayDate = new Date().toISOString().split("T")[0];

  const refresh = useCallback(
    async (currentProjectId: string | null) => {
      const online = await syncService.isOnline();
      const diary = currentProjectId ? await getDiaryForProjectAndDate(db, currentProjectId, todayDate) : null;
      const pending = await countPendingSyncEntries(db);
      const conflicts = await countUnresolvedConflicts(db);

      setIsOnline(online);
      setTodayDiary(diary);
      setPendingCount(pending);
      setConflictCount(conflicts);
    },
    [db, syncService, todayDate]
  );

  useEffect(() => {
    (async () => {
      const stored = await SecureStore.getItemAsync(PROJECT_ID_KEY);
      setProjectId(stored);
      await refresh(stored);
      setIsLoading(false);
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Re-checks status every time this screen regains focus -- e.g.
  // coming back from DiaryEntryScreen after a save.
  useFocusEffect(
    useCallback(() => {
      refresh(projectId);
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [projectId])
  );

  async function handleSetProject() {
    const trimmed = projectInput.trim();
    if (!trimmed) return;
    await SecureStore.setItemAsync(PROJECT_ID_KEY, trimmed);
    setProjectId(trimmed);
    await refresh(trimmed);
  }

  async function handleChangeProject() {
    await SecureStore.deleteItemAsync(PROJECT_ID_KEY);
    setProjectId(null);
    setProjectInput("");
  }

  async function handleManualSync() {
    setIsSyncing(true);
    const result = await syncService.runSync();
    await syncService.refreshConflicts();
    await refresh(projectId);
    setIsSyncing(false);
    // eslint-disable-next-line no-console -- placeholder for a real toast/snackbar
    console.log(
      result.skippedOffline
        ? "No connection — nothing to sync right now."
        : `Synced ${result.synced} of ${result.attempted}${result.conflicted > 0 ? `, ${result.conflicted} need review` : ""}.`
    );
  }

  if (isLoading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator />
      </View>
    );
  }

  const statusLabel =
    todayDiary === null
      ? "Not started"
      : todayDiary.status === "synced"
        ? "Synced"
        : todayDiary.status === "draft"
          ? "Saved on this device, not yet synced"
          : todayDiary.status;

  return (
    <View style={styles.container}>
      <SyncStatusBanner pendingCount={pendingCount} conflictCount={conflictCount} isOnline={isOnline} />

      <View style={styles.headerRow}>
        <Pressable onPress={() => navigation.navigate("Conflicts")} style={styles.headerButton}>
          <Text style={styles.headerButtonText}>Conflicts {conflictCount > 0 ? `(${conflictCount})` : ""}</Text>
        </Pressable>
        <Pressable onPress={handleManualSync} style={styles.headerButton} disabled={isSyncing}>
          {isSyncing ? <ActivityIndicator size="small" /> : <Text style={styles.headerButtonText}>Sync now</Text>}
        </Pressable>
      </View>

      {projectId === null ? (
        <View style={styles.centered}>
          <Text style={styles.prompt}>Which project are you on today?</Text>
          <TextInput
            style={styles.input}
            placeholder="Project ID"
            value={projectInput}
            onChangeText={setProjectInput}
          />
          <Pressable style={styles.button} onPress={handleSetProject}>
            <Text style={styles.buttonText}>Continue</Text>
          </Pressable>
        </View>
      ) : (
        <View style={styles.body}>
          <View style={styles.card}>
            <Text style={styles.cardMeta}>Project {projectId}</Text>
            <Text style={styles.cardTitle}>Daily Site Diary</Text>
            <Text style={styles.cardStatus}>{statusLabel}</Text>
            <Pressable
              style={styles.button}
              onPress={() =>
                navigation.navigate("DiaryEntry", { projectId, diaryDate: todayDate, existing: todayDiary })
              }
            >
              <Text style={styles.buttonText}>{todayDiary === null ? "Start today's diary" : "Continue today's diary"}</Text>
            </Pressable>
          </View>
          <Pressable onPress={handleChangeProject} style={styles.linkButton}>
            <Text style={styles.linkText}>Change project</Text>
          </Pressable>
        </View>
      )}
    </View>
  );
}

function SyncStatusBanner({
  pendingCount,
  conflictCount,
  isOnline,
}: {
  pendingCount: number;
  conflictCount: number;
  isOnline: boolean;
}) {
  if (pendingCount === 0 && conflictCount === 0 && isOnline) return null;

  let background: string;
  let message: string;
  if (conflictCount > 0) {
    background = colors.brickDim;
    message = `${conflictCount} item${conflictCount === 1 ? "" : "s"} need${conflictCount === 1 ? "s" : ""} your review`;
  } else if (!isOnline) {
    background = colors.amberDim;
    message = `Offline — ${pendingCount} item${pendingCount === 1 ? "" : "s"} waiting to sync`;
  } else {
    background = colors.steelDim;
    message = `Syncing ${pendingCount} item${pendingCount === 1 ? "" : "s"}…`;
  }

  return (
    <View style={[styles.banner, { backgroundColor: background }]}>
      <Text style={styles.bannerText}>{message}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.paper },
  centered: { flex: 1, alignItems: "center", justifyContent: "center", padding: 24 },
  headerRow: { flexDirection: "row", justifyContent: "flex-end", padding: 12, gap: 16 },
  headerButton: { paddingHorizontal: 8, paddingVertical: 4 },
  headerButtonText: { color: colors.steel, fontWeight: "600" },
  banner: { paddingHorizontal: 16, paddingVertical: 10 },
  bannerText: { fontWeight: "600" },
  body: { padding: 16 },
  card: { backgroundColor: colors.white, borderRadius: 3, borderWidth: 1, borderColor: colors.line, padding: 16 },
  cardMeta: { color: colors.navy600 },
  cardTitle: { fontSize: 18, fontWeight: "bold", marginTop: 8 },
  cardStatus: { color: colors.steel, marginTop: 4, marginBottom: 16 },
  prompt: { fontSize: 16, fontWeight: "600", marginBottom: 12, textAlign: "center" },
  input: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 3,
    padding: 12,
    fontSize: 16,
    width: "100%",
    marginBottom: 16,
  },
  button: { backgroundColor: colors.navy900, borderRadius: 3, padding: 14, alignItems: "center" },
  buttonText: { color: colors.white, fontWeight: "600" },
  linkButton: { marginTop: 12, alignItems: "center" },
  linkText: { color: colors.steel },
});
