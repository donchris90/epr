import React, { useState } from "react";
import { View, Text, TextInput, Pressable, ActivityIndicator, StyleSheet, ScrollView } from "react-native";
import * as SQLite from "expo-sqlite";
import { v4 as uuidv4 } from "uuid";

import { upsertLocalDiary, insertSyncQueueEntry } from "../db/database";
import { SyncService } from "../sync/syncService";
import { colors } from "../theme/colors";
import type { DiaryEntryScreenProps } from "../navigation/types";

/** Captures today's Daily Site Diary (SRS 7.2.2) for one project.
 * Always saves locally first, then queues for sync -- the whole
 * point of offline-first: a save must never fail just because the
 * device has no signal. See sync/syncService.ts for the upload half,
 * and backend/app/modules/mfa/services.py:_create_exe_daily_site_diary
 * for exactly what the server does with this once it arrives. */
interface Props extends DiaryEntryScreenProps {
  db: SQLite.SQLiteDatabase;
  syncService: SyncService;
}

export default function DiaryEntryScreen({ db, syncService, route, navigation }: Props) {
  const { projectId, diaryDate, existing } = route.params;

  const [workforceCount, setWorkforceCount] = useState(existing?.workforce_present_count?.toString() ?? "");
  const [equipmentSummary, setEquipmentSummary] = useState(existing?.equipment_on_site_summary ?? "");
  const [narrative, setNarrative] = useState(existing?.narrative ?? "");
  const [isSaving, setIsSaving] = useState(false);

  const isEditingSyncedEntry = existing?.status === "synced";

  async function handleSave() {
    setIsSaving(true);

    // Reuses the existing local record's own client_uuid if editing a
    // draft already captured today, rather than minting a new one --
    // otherwise a second save of the same day's diary would look
    // like an entirely different record to the server's idempotency
    // check.
    const clientRecordId = existing?.client_uuid ?? uuidv4();

    const parsedWorkforce = workforceCount.trim() ? parseInt(workforceCount.trim(), 10) : null;
    const trimmedEquipment = equipmentSummary.trim();
    const trimmedNarrative = narrative.trim();

    const payload: Record<string, unknown> = { project_id: projectId, diary_date: diaryDate };
    if (parsedWorkforce !== null && !Number.isNaN(parsedWorkforce)) payload.workforce_present_count = parsedWorkforce;
    if (trimmedEquipment) payload.equipment_on_site_summary = trimmedEquipment;
    if (trimmedNarrative) payload.narrative = trimmedNarrative;

    await upsertLocalDiary(db, {
      client_uuid: clientRecordId,
      project_id: projectId,
      diary_date: diaryDate,
      workforce_present_count: Number.isNaN(parsedWorkforce as number) ? null : parsedWorkforce,
      equipment_on_site_summary: trimmedEquipment || null,
      narrative: trimmedNarrative || null,
      status: "draft",
      server_record_id: existing?.server_record_id ?? null,
    });

    await insertSyncQueueEntry(db, {
      id: uuidv4(),
      target_module: "EXE",
      target_entity_type: "exe_daily_site_diary",
      client_record_id: clientRecordId,
      operation: "create",
      payload_json: JSON.stringify(payload),
      device_timestamp: new Date().toISOString(),
      status: "pending",
      rejection_reason: null,
    });

    // A real, immediate attempt if there's connectivity -- but the
    // save above already happened regardless of what this returns.
    // A failed or offline sync attempt here is not a failed save.
    const result = await syncService.runSync();

    setIsSaving(false);

    const message = result.skippedOffline
      ? "Saved on this device. Will sync once you're back online."
      : result.conflicted > 0
        ? "Saved, but the server found a conflict — check the Conflicts screen."
        : "Saved and synced.";

    // React Native has no built-in blocking alert equivalent to a web
    // toast in this minimal setup -- a real app would use a toast
    // library; for now this is surfaced via a simple inline banner
    // pattern the caller (TodayScreen) can extend.
    navigation.navigate("Today");
    // eslint-disable-next-line no-console -- placeholder for a real toast/snackbar
    console.log(message);
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {isEditingSyncedEntry && (
        <View style={styles.notice}>
          <Text>
            This diary already synced. Changes here will be sent as a new sync entry — the server does not yet support
            editing an already-synced diary through this app; use the web app for that.
          </Text>
        </View>
      )}

      <Text style={styles.meta}>Project: {projectId}</Text>
      <Text style={styles.meta}>Date: {diaryDate}</Text>

      <Text style={styles.label}>Workforce present today</Text>
      <TextInput
        style={styles.input}
        keyboardType="number-pad"
        value={workforceCount}
        onChangeText={setWorkforceCount}
      />

      <Text style={styles.label}>Equipment on site</Text>
      <TextInput
        style={[styles.input, styles.multiline]}
        multiline
        numberOfLines={3}
        placeholder="e.g. 2 excavators, 1 crane"
        value={equipmentSummary}
        onChangeText={setEquipmentSummary}
      />

      <Text style={styles.label}>Narrative</Text>
      <TextInput
        style={[styles.input, styles.multilineLarge]}
        multiline
        numberOfLines={6}
        value={narrative}
        onChangeText={setNarrative}
      />

      <Pressable style={[styles.button, isSaving && styles.buttonDisabled]} onPress={handleSave} disabled={isSaving}>
        {isSaving ? <ActivityIndicator color={colors.white} /> : <Text style={styles.buttonText}>Save</Text>}
      </Pressable>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.paper },
  content: { padding: 16 },
  notice: { backgroundColor: colors.amberDim, borderRadius: 3, padding: 12, marginBottom: 16 },
  meta: { color: colors.navy600, marginBottom: 4 },
  label: { marginTop: 16, marginBottom: 6, fontWeight: "600", color: colors.navy800 },
  input: { backgroundColor: colors.white, borderWidth: 1, borderColor: colors.line, borderRadius: 3, padding: 12, fontSize: 16 },
  multiline: { minHeight: 72, textAlignVertical: "top" },
  multilineLarge: { minHeight: 140, textAlignVertical: "top" },
  button: { backgroundColor: colors.navy900, borderRadius: 3, padding: 16, alignItems: "center", marginTop: 24 },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: colors.white, fontSize: 16, fontWeight: "600" },
});
