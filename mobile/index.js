/**
 * TODOlist Mobile App - Entry point
 * React Native + React Navigation + React Query
 */
import React from "react";
import { AppRegistry } from "react-native";
import { PaperProvider, DefaultTheme } from "react-native-paper";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NavigationContainer } from "@react-navigation/native";
import App from "./src/App";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 30000,
    },
  },
});

const theme = {
  ...DefaultTheme,
  colors: {
    ...DefaultTheme.colors,
    primary: "#1976d2",
    accent: "#43a047",
  },
};

function Main() {
  return (
    <QueryClientProvider client={queryClient}>
      <PaperProvider theme={theme}>
        <NavigationContainer>
          <App />
        </NavigationContainer>
      </PaperProvider>
    </QueryClientProvider>
  );
}

AppRegistry.registerComponent("todolist", () => Main);
