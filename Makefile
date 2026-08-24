# ============================================================
#  TODOlist - Makefile
#  Comandos habituales para desarrollo, tests, build y deploy
# ============================================================

# Variables
PYTHON        := python
PIP           := pip
MANAGE        := cd backend && $(PYTHON) manage.py
VENV          := backend/.venv
VENV_PYTHON   := $(VENV)/Scripts/python.exe
VENV_PIP      := $(VENV)/Scripts/pip.exe
FRONTEND_DIR  := frontend
DOCKER_COMPOSE := docker compose

# Colores
HELP_COLOR    := \033[36m
RESET         := \033[0m

# Detectar OS para comandos de activación de venv
ifeq ($(OS),Windows_NT)
    ACTIVATE_VENV := $$env:VIRTUAL_ENV=\"$$(pwd)\backend\.venv\"; $$env:PATH=\"$$(pwd)\backend\.venv\Scripts;$$env:PATH\"
else
    ACTIVATE_VENV := source backend/.venv/bin/activate
endif

# ============================================================
#  HELP
# ============================================================

.PHONY: help
help: ## Muestra esta ayuda
	@echo ""
	@echo "  TODOlist - Comandos disponibles:"
	@echo ""
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(HELP_COLOR)%-25s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "  Ejemplo: make setup && make dev"
	@echo ""

# ============================================================
#  SETUP - Instalación inicial
# ============================================================

.PHONY: setup
setup: setup-backend setup-frontend ## Instalación completa: backend + frontend

.PHONY: setup-backend
setup-backend: ## Crea venv e instala dependencias del backend
	@echo ">>> Configurando backend..."
	$(PYTHON) -m venv $(VENV)
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -r backend/requirements.txt
	@echo ">>> Backend listo."

.PHONY: setup-frontend
setup-frontend: ## Instala dependencias del frontend
	@echo ">>> Configurando frontend..."
	cd $(FRONTEND_DIR) && npm install
	@echo ">>> Frontend listo."

.PHONY: env
env: ## Copia .env.example a .env (ajustar valores antes de producción)
	@if [ ! -f backend/.env ]; then cp .env.example backend/.env; echo ">>> backend/.env creado desde .env.example"; \
	else echo ">>> backend/.env ya existe (no se sobrescribe)"; fi

# ============================================================
#  DESARROLLO LOCAL
# ============================================================

.PHONY: dev
dev: ## Levanta backend + frontend en paralelo (modo desarrollo)
	@echo ">>> Iniciando backend (http://localhost:8000) y frontend (http://localhost:5173)..."
	@$(MAKE) -j2 dev-backend dev-frontend

.PHONY: dev-backend
dev-backend: ## Levanta solo el backend (Django dev server)
	@echo ">>> Backend en http://localhost:8000"
	cd backend && $(VENV_PYTHON) manage.py runserver 0.0.0.0:8000

.PHONY: dev-frontend
dev-frontend: ## Levanta solo el frontend (Vite dev server)
	@echo ">>> Frontend en http://localhost:5173"
	cd $(FRONTEND_DIR) && npm run dev

# ============================================================
#  DOCKER
# ============================================================

.PHONY: docker-up
docker-up: ## Levanta todos los servicios con Docker Compose (db, redis, backend, frontend)
	$(DOCKER_COMPOSE) up --build

.PHONY: docker-up-d
docker-up-d: ## Levanta Docker Compose en background (detached)
	$(DOCKER_COMPOSE) up --build -d

.PHONY: docker-down
docker-down: ## Detiene y elimina contenedores de Docker Compose
	$(DOCKER_COMPOSE) down

.PHONY: docker-logs
docker-logs: ## Muestra logs de Docker Compose (tail -f)
	$(DOCKER_COMPOSE) logs -f

.PHONY: docker-ps
docker-ps: ## Lista contenedores en ejecución
	$(DOCKER_COMPOSE) ps

.PHONY: docker-rebuild
docker-rebuild: ## Reconstruye imágenes de Docker sin caché
	$(DOCKER_COMPOSE) build --no-cache

.PHONY: docker-shell-backend
docker-shell-backend: ## Abre shell en el contenedor del backend
	$(DOCKER_COMPOSE) exec backend bash

.PHONY: docker-shell-db
docker-shell-db: ## Abre psql en el contenedor de PostgreSQL
	$(DOCKER_COMPOSE) exec db psql -U todolist -d todolist

# ============================================================
#  BASE DE DATOS (local con venv)
# ============================================================

.PHONY: migrate
migrate: ## Aplica migraciones de Django
	cd backend && $(VENV_PYTHON) manage.py migrate

.PHONY: makemigrations
makemigrations: ## Genera migraciones nuevas
	cd backend && $(VENV_PYTHON) manage.py makemigrations

.PHONY: makemigrations-dry
makemigrations-dry: ## Muestra qué migraciones se generarían (sin aplicar)
	cd backend && $(VENV_PYTHON) manage.py makemigrations --dry-run

.PHONY: seed
seed: ## Carga datos de ejemplo (seed_dev)
	cd backend && $(VENV_PYTHON) manage.py seed_dev

.PHONY: shell
shell: ## Abre Django shell
	cd backend && $(VENV_PYTHON) manage.py shell

.PHONY: dbshell
dbshell: ## Abre consola de base de datos (Django dbshell)
	cd backend && $(VENV_PYTHON) manage.py dbshell

.PHONY: superuser
superuser: ## Crea un superusuario interactivo
	cd backend && $(VENV_PYTHON) manage.py createsuperuser

# ============================================================
#  TESTS
# ============================================================

.PHONY: test
test: test-backend test-frontend ## Ejecuta todos los tests (backend + frontend)

.PHONY: test-backend
test-backend: ## Tests del backend con pytest
	@echo ">>> Ejecutando tests del backend..."
	cd backend && $(VENV_PYTHON) -m pytest tests/ -v

.PHONY: test-backend-fast
test-backend-fast: ## Tests del backend sin verbose (rápido)
	cd backend && $(VENV_PYTHON) -m pytest tests/ -q

.PHONY: test-backend-cov
test-backend-cov: ## Tests del backend con cobertura
	cd backend && $(VENV_PYTHON) -m pytest tests/ --cov=apps --cov-report=term-missing

.PHONY: test-frontend
test-frontend: ## Tests del frontend con vitest
	@echo ">>> Ejecutando tests del frontend..."
	cd $(FRONTEND_DIR) && npx vitest run

.PHONY: test-watch
test-watch: ## Tests del frontend en modo watch
	cd $(FRONTEND_DIR) && npx vitest

.PHONY: test-e2e
test-e2e: ## Tests E2E con Playwright (requiere navegador instalado)
	cd $(FRONTEND_DIR) && npx playwright install chromium
	cd $(FRONTEND_DIR) && npx playwright test

# ============================================================
#  BUILD
# ============================================================

.PHONY: build
build: build-frontend build-backend ## Build completo (frontend + collectstatic)

.PHONY: build-frontend
build-frontend: ## Build del frontend (Vite → dist/)
	@echo ">>> Build del frontend..."
	cd $(FRONTEND_DIR) && npm run build

.PHONY: build-backend
build-backend: ## Collectstatic del backend para producción
	@echo ">>> Collectstatic del backend..."
	cd backend && $(VENV_PYTHON) manage.py collectstatic --noinput

.PHONY: build-docker
build-docker: ## Construye imágenes Docker de backend y frontend
	@echo ">>> Construyendo imágenes Docker..."
	$(DOCKER_COMPOSE) build

# ============================================================
#  LINT Y CALIDAD
# ============================================================

.PHONY: lint
lint: lint-frontend typecheck ## Lint + typecheck del frontend

.PHONY: lint-frontend
lint-frontend: ## ESLint del frontend
	cd $(FRONTEND_DIR) && npx eslint . --ext ts,tsx

.PHONY: typecheck
typecheck: ## TypeScript type-check (sin emitir JS)
	cd $(FRONTEND_DIR) && npx tsc -b --noEmit

.PHONY: check
check: ## Django system check
	cd backend && $(VENV_PYTHON) manage.py check

# ============================================================
#  PRODUCCIÓN (Docker Compose prod)
# ============================================================

.PHONY: prod-up
prod-up: ## Levanta en modo producción (gunicorn + nginx, sin hot-reload)
	@echo ">>> Levantando en modo producción..."
	$(DOCKER_COMPOSE) -f docker-compose.prod.yml up --build -d
	@echo ">>> Aplicación disponible en http://localhost"
	@echo ">>> API en http://localhost/api/"

.PHONY: prod-down
prod-down: ## Detiene el entorno de producción
	$(DOCKER_COMPOSE) -f docker-compose.prod.yml down

.PHONY: prod-logs
prod-logs: ## Logs del entorno de producción
	$(DOCKER_COMPOSE) -f docker-compose.prod.yml logs -f

.PHONY: prod-migrate
prod-migrate: ## Aplica migraciones en el contenedor de producción
	$(DOCKER_COMPOSE) -f docker-compose.prod.yml exec backend python manage.py migrate

# ============================================================
#  KUBERNETES
# ============================================================

.PHONY: k8s-apply
k8s-apply: ## Aplica manifests de Kubernetes (requiere kubectl + cluster)
	kubectl apply -f deploy/k8s/

.PHONY: k8s-delete
k8s-delete: ## Elimina recursos de Kubernetes
	kubectl delete -f deploy/k8s/

.PHONY: k8s-status
k8s-status: ## Estado de pods y servicios en K8s
	kubectl get pods,svc,ingress -n todolist

.PHONY: helm-install
helm-install: ## Instala el chart de Helm
	helm install todolist deploy/helm/todolist

.PHONY: helm-upgrade
helm-upgrade: ## Actualiza el release de Helm
	helm upgrade todolist deploy/helm/todolist

.PHONY: helm-uninstall
helm-uninstall: ## Desinstala el chart de Helm
	helm uninstall todolist

# ============================================================
#  TERRAFORM
# ============================================================

.PHONY: tf-init
tf-init: ## Inicializa Terraform
	cd deploy/terraform && terraform init

.PHONY: tf-plan
tf-plan: ## Plan de Terraform (muestra cambios sin aplicar)
	cd deploy/terraform && terraform plan

.PHONY: tf-apply
tf-apply: ## Aplica la infraestructura de Terraform
	cd deploy/terraform && terraform apply

.PHONY: tf-destroy
tf-destroy: ## Destruye toda la infraestructura de Terraform (¡cuidado!)
	cd deploy/terraform && terraform destroy

# ============================================================
#  UTILIDADES
# ============================================================

.PHONY: clean
clean: ## Limpia archivos generados (__pycache__, dist, staticfiles, .pytest_cache)
	@echo ">>> Limpiando archivos generados..."
	find backend -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find backend -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf frontend/dist
	rm -rf backend/staticfiles
	@echo ">>> Limpieza completada."

.PHONY: clean-db
clean-db: ## Borra la base de datos SQLite local (¡cuidado!)
	rm -f backend/db.sqlite3
	@echo ">>> db.sqlite3 eliminada."

.PHONY: requirements
requirements: ## Actualiza requirements.txt desde pip freeze (solo si usas venv)
	$(VENV_PIP) freeze > backend/requirements.txt

.PHONY: graph
graph: ## Genera diagrama de dependencias de migraciones
	cd backend && $(VENV_PYTHON) manage.py makemigrations --dry-run -v 3

# ============================================================
#  DEPLOY (Render / Railway / Fly.io)
# ============================================================

.PHONY: deploy-render
deploy-render: build ## Prepara el build para desplegar en Render (usa Dockerfile)
	@echo ">>> Build listo para Render."
	@echo ">>> Configura en Render:"
	@echo "    Backend:  Dockerfile en backend/  →  Puerto 8000"
	@echo "    Frontend: Dockerfile en frontend/ →  Puerto 80"
	@echo "    DB:       PostgreSQL gestionado por Render"
	@echo "    Redis:    Redis gestionado por Render"
	@echo ">>> Variables de entorno necesarias:"
	@echo "    DJANGO_SECRET_KEY, DJANGO_DEBUG=0, DJANGO_ALLOWED_HOSTS"
	@echo "    POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD"
	@echo "    REDIS_HOST, REDIS_PORT"
	@echo "    DJANGO_FRONTEND_URL (URL pública del frontend)"
	@echo "    VITE_API_URL (URL pública del backend /api)"

.PHONY: deploy-fly
deploy-fly: ## Despliega a Fly.io (requiere flyctl instalado y autenticado)
	@echo ">>> Desplegando a Fly.io..."
	@which fly >/dev/null 2>&1 || { echo "ERROR: flyctl no instalado. Instala con: curl -L https://fly.io/install.sh | sh"; exit 1; }
	fly deploy

# ============================================================
#  ATAJOS
# ============================================================

.PHONY: fresh
fresh: setup migrate seed ## Setup + migraciones + seed (empezar desde cero)

.PHONY: all
all: check test build ## Check + tests + build (verificación completa)

.PHONY: ci
ci: typecheck test-frontend test-backend-fast build ## Simula CI localmente
	@echo ">>> CI local completado."
