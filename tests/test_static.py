import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_python_syntax():
    for path in (ROOT / "app").rglob("*.py"):
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_compose_and_docker_files():
    compose = (ROOT / "docker-compose.yml").read_text()
    assert "image: postgres:16-alpine" in compose
    assert "condition: service_healthy" in compose
    assert "app.main" in (ROOT / "Dockerfile").read_text()


def test_psycopg3_dialect():
    text = (ROOT / "app/core/database.py").read_text()
    assert 'postgresql+psycopg://' in text
    assert 'postgresql+psycopg2://' not in text


def test_env_is_not_packaged():
    assert not (ROOT / '.env').exists()
