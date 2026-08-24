/**
 * App principal con navegación por tabs
 */
import React from "react";
import { createBottomTabNavigator } from "@react-navigation/bottom-tabs";
import Icon from "react-native-vector-icons/MaterialIcons";

import TaskListScreen from "./screens/TaskListScreen";
import ProjectsScreen from "./screens/ProjectsScreen";
import DashboardScreen from "./screens/DashboardScreen";
import SettingsScreen from "./screens/SettingsScreen";

const Tab = createBottomTabNavigator();

export default function App() {
  return (
    <Tab.Navigator
      screenOptions={({ route }) => ({
        tabBarIcon: ({ color, size }) => {
          const icons = {
            Tasks: "check-circle",
            Projects: "folder",
            Dashboard: "dashboard",
            Settings: "settings",
          };
          return <Icon name={icons[route.name] || "circle"} size={size} color={color} />;
        },
        tabBarActiveTintColor: "#1976d2",
        tabBarInactiveTintColor: "gray",
      })}
    >
      <Tab.Screen name="Tasks" component={TaskListScreen} options={{ title: "Tareas" }} />
      <Tab.Screen name="Projects" component={ProjectsScreen} options={{ title: "Proyectos" }} />
      <Tab.Screen name="Dashboard" component={DashboardScreen} options={{ title: "Dashboard" }} />
      <Tab.Screen name="Settings" component={SettingsScreen} options={{ title: "Ajustes" }} />
    </Tab.Navigator>
  );
}
