import type { NativeStackScreenProps } from "@react-navigation/native-stack";
import type { LocalDiary } from "../db/database";

export type RootStackParamList = {
  Login: undefined;
  Today: undefined;
  DiaryEntry: { projectId: string; diaryDate: string; existing: LocalDiary | null };
  Conflicts: undefined;
};

export type LoginScreenProps = NativeStackScreenProps<RootStackParamList, "Login">;
export type TodayScreenProps = NativeStackScreenProps<RootStackParamList, "Today">;
export type DiaryEntryScreenProps = NativeStackScreenProps<RootStackParamList, "DiaryEntry">;
export type ConflictsScreenProps = NativeStackScreenProps<RootStackParamList, "Conflicts">;
