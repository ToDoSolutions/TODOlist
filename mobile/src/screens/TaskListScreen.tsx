/**
 * TaskListScreen - Lista de tareas
 */
import React from "react";
import { View, Text, FlatList, TouchableOpacity, StyleSheet, RefreshControl } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { Card, Title, Paragraph, FAB, ActivityIndicator, Chip } from "react-native-paper";
import { tasksApi } from "../api";

export default function TaskListScreen({ navigation }: any) {
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["tasks"],
    queryFn: tasksApi.list,
  });

  const tasks = data?.results || data || [];

  const stateColors: Record<string, string> = {
    pending: "#ff9800",
    in_progress: "#2196f3",
    completed: "#4caf50",
    blocked: "#f44336",
  };

  if (isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" />
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={tasks}
        keyExtractor={(item: any) => item.id.toString()}
        refreshControl={<RefreshControl refreshing={isFetching} onRefresh={refetch} />}
        renderItem={({ item }: any) => (
          <TouchableOpacity onPress={() => navigation.navigate("TaskDetail", { taskId: item.id })}>
            <Card style={styles.card}>
              <Card.Content>
                <View style={styles.row}>
                  <Title style={styles.title}>{item.title}</Title>
                  <Chip style={[styles.chip, { backgroundColor: stateColors[item.state] || "#999" }]}>
                    {item.state}
                  </Chip>
                </View>
                {item.description ? <Paragraph>{item.description}</Paragraph> : null}
                {item.due_date ? <Text style={styles.dueDate}>Vence: {item.due_date}</Text> : null}
              </Card.Content>
            </Card>
          </TouchableOpacity>
        )}
      />
      <FAB icon="plus" style={styles.fab} onPress={() => navigation.navigate("CreateTask")} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#f5f5f5" },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },
  card: { margin: 8, elevation: 2 },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  title: { flex: 1, fontSize: 16 },
  chip: { height: 24 },
  dueDate: { color: "#666", fontSize: 12, marginTop: 4 },
  fab: { position: "absolute", margin: 16, right: 0, bottom: 0, backgroundColor: "#1976d2" },
});
