# EventQR — Laboratorio resuelto

Sistema modular con NiceGUI, SQLModel, PostgreSQL, Docker Compose, escáner QR y reportes CSV.

## 1. Ejecución local en Windows / VS Code

1. Instala y abre Docker Desktop. Comprueba `docker --version` y `docker compose version`.
2. Abre una terminal PowerShell en esta carpeta.
3. Copia el archivo de ejemplo: `Copy-Item .env.example .env`
4. Edita `.env` y cambia `STORAGE_SECRET` por una cadena aleatoria larga.
5. Ejecuta `docker compose up --build -d`.
6. Abre http://localhost:8080.
7. Si no abre, revisa `docker compose logs -f web`. Si el puerto 8080 está ocupado cambia `APP_PORT=8081` en `.env` y usa http://localhost:8081.
8. Para detener: `docker compose down` (sin `-v` para no borrar los datos).

## 2. Comprobación / capturas

- Crea un evento y captura la tabla de eventos.
- Inscribe un participante y descarga su QR (PNG); captura el formulario y QR.
- Abre Check-in, prueba el QR con la cámara o pega su UUID; captura el éxito.
- Repite el mismo QR en la misma fecha; captura el mensaje de duplicado.
- Abre Reportes, selecciona el evento y descarga el CSV; captura la tabla.
- Captura `docker compose ps` con los servicios en ejecución.

La cámara del navegador funciona con localhost o con HTTPS; un teléfono conectado por HTTP a una IP local normalmente no podrá usar la cámara.

## 3. Despliegue opcional Supabase + GitHub + Render (según la guía)

1. Crea una base de datos en Supabase; copia su `DATABASE_URL` y guárdala de forma privada.
2. Sube el código a GitHub sin `.env` (ya está en `.gitignore`). Usa un repositorio **privado** si no quieres exponer el código.
3. En Render crea un Web Service Docker desde el repositorio. Establece `DATABASE_URL`, `STORAGE_SECRET` y `APP_TITLE` en las variables de entorno. Render utiliza solamente el Dockerfile (no docker-compose).
4. Si usas el *transaction pooler* de Supabase, configura `DB_USE_NULLPOOL=true`. El puerto debe coincidir con el modo de conexión que te facilita Supabase.
5. Verifica la URL HTTPS de Render probando la creación de eventos y el check-in.

**Seguridad:** La práctica no implementa autenticación ni permisos. No publiques datos reales de participantes en un despliegue accesible a cualquiera. Para usos reales agrega inicio de sesión, autorización y protección de datos personales.

**Nota sobre credenciales:** El ZIP original incluía un `.env` y una carpeta `.git`. Se han excluido ambos de esta entrega. Si esas credenciales eran reales o se publicaron alguna vez, cámbialas en Supabase y en los servicios correspondientes.
