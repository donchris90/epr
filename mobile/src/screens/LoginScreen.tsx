import React, { useState } from "react";
import { View, Text, TextInput, Pressable, ActivityIndicator, StyleSheet, KeyboardAvoidingView, Platform } from "react-native";
import { AxiosError } from "axios";

import { ApiClient } from "../api/apiClient";
import { colors } from "../theme/colors";
import type { LoginScreenProps } from "../navigation/types";

interface Props extends LoginScreenProps {
  apiClient: ApiClient;
}

export default function LoginScreen({ apiClient, navigation }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  async function handleSubmit() {
    setIsLoading(true);
    setErrorMessage(null);

    try {
      await apiClient.login(email.trim(), password);
      navigation.replace("Today");
    } catch (err) {
      // A 401 here is "Invalid credentials" per the real backend
      // (backend/app/auth/routes.py) -- anything else (timeout, no
      // connectivity, 5xx) gets a distinct, honest message rather
      // than being folded into the same "wrong password" text.
      const status = err instanceof AxiosError ? err.response?.status : undefined;
      setErrorMessage(
        status === 401 ? "Incorrect email or password." : "Could not reach the server. Check your connection and try again."
      );
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <KeyboardAvoidingView style={styles.flex} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <View style={styles.container}>
        <Text style={styles.title}>SiteForge Field</Text>

        <TextInput
          style={styles.input}
          placeholder="Email"
          autoCapitalize="none"
          autoCorrect={false}
          keyboardType="email-address"
          value={email}
          onChangeText={setEmail}
        />
        <TextInput
          style={styles.input}
          placeholder="Password"
          secureTextEntry
          value={password}
          onChangeText={setPassword}
          onSubmitEditing={isLoading ? undefined : handleSubmit}
        />

        {errorMessage && <Text style={styles.error}>{errorMessage}</Text>}

        <Pressable style={[styles.button, isLoading && styles.buttonDisabled]} onPress={handleSubmit} disabled={isLoading}>
          {isLoading ? <ActivityIndicator color={colors.white} /> : <Text style={styles.buttonText}>Sign in</Text>}
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  container: { flex: 1, justifyContent: "center", padding: 24, backgroundColor: colors.paper },
  title: { fontSize: 28, fontWeight: "bold", color: colors.navy900, textAlign: "center", marginBottom: 32 },
  input: {
    backgroundColor: colors.white,
    borderWidth: 1,
    borderColor: colors.line,
    borderRadius: 3,
    padding: 14,
    marginBottom: 12,
    fontSize: 16,
  },
  error: { color: colors.brick, marginBottom: 12 },
  button: {
    backgroundColor: colors.navy900,
    borderRadius: 3,
    padding: 16,
    alignItems: "center",
    marginTop: 8,
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { color: colors.white, fontSize: 16, fontWeight: "600" },
});
