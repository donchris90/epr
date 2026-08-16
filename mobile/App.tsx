import React, { useEffect, useState } from "react";
import { View, ActivityIndicator } from "react-native";
import { NavigationContainer } from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import * as SQLite from "expo-sqlite";

import { ApiClient } from "./src/api/apiClient";
import { getDatabase } from "./src/db/database";
import { SyncService } from "./src/sync/syncService";
import { colors } from "./src/theme/colors";
import type { RootStackParamList } from "./src/navigation/types";

import LoginScreen from "./src/screens/LoginScreen";
import TodayScreen from "./src/screens/TodayScreen";
import DiaryEntryScreen from "./src/screens/DiaryEntryScreen";
import ConflictsScreen from "./src/screens/ConflictsScreen";

const Stack = createNativeStackNavigator<RootStackParamList>();

/** SiteForge Mobile Field App (SRS Module 24).
 *
 * Offline-first by design (SRS Section 2.4 / 3.5): the app maintains
 * a local SQLite database (see src/db/) mirroring the subset of
 * server data relevant to the logged-in user's assigned projects,
 * and queues writes locally for background sync (see src/sync/). */
export default function App() {
  const [isReady, setIsReady] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [apiClient] = useState(() => new ApiClient());
  const [db, setDb] = useState<SQLite.SQLiteDatabase | null>(null);
  const [syncService, setSyncService] = useState<SyncService | null>(null);

  useEffect(() => {
    (async () => {
      const database = await getDatabase();
      const sync = new SyncService(apiClient, database, "mobile-device");
      const loggedIn = await apiClient.isLoggedIn();

      setDb(database);
      setSyncService(sync);
      setIsLoggedIn(loggedIn);
      setIsReady(true);
    })();
  }, [apiClient]);

  if (!isReady || !db || !syncService) {
    return (
      <View style={{ flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.paper }}>
        <ActivityIndicator size="large" color={colors.navy900} />
      </View>
    );
  }

  return (
    <NavigationContainer>
      <Stack.Navigator initialRouteName={isLoggedIn ? "Today" : "Login"} screenOptions={{ headerTintColor: colors.white }}>
        <Stack.Screen name="Login" options={{ headerShown: false }}>
          {(props) => <LoginScreen {...props} apiClient={apiClient} />}
        </Stack.Screen>
        <Stack.Screen
          name="Today"
          options={{ title: "Today", headerStyle: { backgroundColor: colors.navy900 } }}
        >
          {(props) => <TodayScreen {...props} db={db} apiClient={apiClient} syncService={syncService} />}
        </Stack.Screen>
        <Stack.Screen
          name="DiaryEntry"
          options={{ title: "Daily Site Diary", headerStyle: { backgroundColor: colors.navy900 } }}
        >
          {(props) => <DiaryEntryScreen {...props} db={db} syncService={syncService} />}
        </Stack.Screen>
        <Stack.Screen
          name="Conflicts"
          options={{ title: "Conflicts", headerStyle: { backgroundColor: colors.navy900 } }}
        >
          {() => <ConflictsScreen apiClient={apiClient} />}
        </Stack.Screen>
      </Stack.Navigator>
    </NavigationContainer>
  );
}
