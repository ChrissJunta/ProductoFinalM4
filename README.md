# ProductoFinalM4 — MVP Mesa de Ayuda Omnicanal

Especificación: [`SPEC_MVP_Mesa_Ayuda_v5_2_PostgreSQL_Tareas.md`](SPEC_MVP_Mesa_Ayuda_v5_2_PostgreSQL_Tareas.md)
Coordinación entre agentes, contratos de vista y estado de tareas: [`progress.md`](progress.md)

## Requisitos

- Python 3.12+
- PostgreSQL 16

## Puesta en marcha (backend)

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                 # ajustar credenciales de PostgreSQL

# crear la base de datos (una vez)
createdb -U postgres -O helpdesk helpdesk

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

## Pruebas

```bash
pytest --cov
ruff check . && ruff format --check .
```

Las pruebas usan PostgreSQL real (`config.settings.test`); CI ejecuta lo mismo en GitHub Actions.
