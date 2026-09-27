"""Test de carga con Locust — escenarios realistas de uso.

Uso:
    pip install locust
    locust -f locustfile.py --host http://localhost:8000

Endpoints críticos cubiertos: login, listado de tareas (con relaciones),
kanban (filtro por estado), dashboard metrics, sync push/pull.
Los usuarios se registran al arrancar (1 por worker user).
"""
import random
import uuid

from locust import HttpUser, between, task


class TaskUser(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        suffix = uuid.uuid4().hex[:8]
        self.email = f"load_{suffix}@load.test"
        resp = self.client.post("/api/auth/register/", json={
            "email": self.email,
            "username": f"load_{suffix}",
            "password": "LoadTest123!",
        })
        if resp.status_code in (200, 201):
            data = resp.json()
            token = data.get("access")
            if token:
                self.client.headers["Authorization"] = f"Bearer {token}"
        # Semilla de datos: proyecto + tareas para que las lecturas no sean vacías
        self.client.post("/api/projects/", json={"name": "Load"})
        for i in range(20):
            self.client.post("/api/tasks/", json={
                "title": f"tarea {i}",
                "priority": random.randint(1, 6),
            })

    @task(5)
    def list_tasks(self):
        self.client.get("/api/tasks/")

    @task(3)
    def kanban_pending(self):
        self.client.get("/api/tasks/?state=pending")

    @task(2)
    def dashboard(self):
        self.client.get("/api/metrics/dashboard/")

    @task(2)
    def list_projects(self):
        self.client.get("/api/projects/")

    @task(1)
    def sync_pull(self):
        self.client.get("/api/sync/pull/")

    @task(1)
    def sync_push(self):
        self.client.post("/api/sync/push/", json={"operations": [{
            "op_type": "update", "entity_type": "task",
            "entity_id": str(random.randint(1, 20)),
            "payload": {"title": "from-load"},
            "device_id": "load-device",
            "base_version": 0,
        }]})
