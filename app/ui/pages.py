"""Interfaz NiceGUI de EventQR: 4 pestañas (Eventos, Inscripción, Check-in, Reportes)."""
from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from nicegui import app, ui

from app.core.config import settings
from app.services import checkin_service, event_service, export_service, qr_service
from app.services.event_service import ValidationError

STATUS_STYLES = {
    checkin_service.SUCCESS: ("bg-green-100 text-green-900", "check_circle", "ACCESO REGISTRADO"),
    checkin_service.DUPLICATE: ("bg-amber-100 text-amber-900", "warning", "YA REGISTRADO HOY"),
    checkin_service.INVALID: ("bg-red-100 text-red-900", "error", "CÓDIGO INVÁLIDO"),
    checkin_service.NOT_FOUND: ("bg-red-100 text-red-900", "block", "NO ENCONTRADO"),
}


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# Escáner por cámara (html5-qrcode se sirve localmente desde /libs).
CAMERA_HEAD_HTML = """
<script src="/libs/html5-qrcode.min.js"></script>
<style>
  #qr-reader { border: none !important; width: 100%; }
  #qr-reader video { width: 100% !important; height: auto !important; display: block; }
</style>
<script>
window.eqr = { scanner: null, last: "", lastAt: 0 };
window.eqrStart = async function (facing) {
  if (window.eqr.scanner) return "ok";
  if (!window.isSecureContext) return "insecure";
  if (typeof Html5Qrcode === "undefined") return "error:No se cargó la librería del escáner.";
  try {
    const scanner = new Html5Qrcode("qr-reader");
    await scanner.start(
      { facingMode: facing || "environment" },
      { fps: 10, qrbox: { width: 240, height: 240 } },
      (text) => {
        const now = Date.now();
        if (text === window.eqr.last && now - window.eqr.lastAt < 4000) return;
        window.eqr.last = text;
        window.eqr.lastAt = now;
        emitEvent("qr_scanned", { text: text });
      },
      () => {}
    );
    window.eqr.scanner = scanner;
    return "ok";
  } catch (err) {
    return "error:" + (err && err.message ? err.message : err);
  }
};
window.eqrStop = async function () {
  const scanner = window.eqr.scanner;
  window.eqr.scanner = null;
  if (scanner) {
    try { await scanner.stop(); scanner.clear(); } catch (e) {}
  }
};
</script>
"""


def _event_options() -> dict[int, str]:
    return {e.id: f"{e.name} · {e.start_date:%d/%m/%Y}" for e in event_service.list_events()}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "participante"


class EventQRPage:
    """Construye la interfaz completa para un cliente (una instancia por pestaña del navegador)."""

    def __init__(self) -> None:
        self._event_selects: list[ui.select] = []
        self._events_table: ui.table | None = None
        self._refresh_participants = lambda: None

    # ------------------------------------------------------------ utilidades
    def _new_event_select(self, label: str = "Evento") -> ui.select:
        select = ui.select(options=_event_options(), label=label).props("outlined dense")
        select.classes("w-full")
        self._event_selects.append(select)
        return select

    def _refresh_event_selects(self) -> None:
        options = _event_options()
        for select in self._event_selects:
            if select.value in options:
                select.set_options(options)
            else:
                select.set_options(options, value=None)

    def _refresh_events_table(self) -> None:
        if self._events_table is not None:
            self._events_table.update_rows(event_service.list_event_summaries())

    # ------------------------------------------------------------- estructura
    def build(self) -> None:
        ui.add_head_html(CAMERA_HEAD_HTML)
        ui.colors(primary="#4338ca")
        with ui.header().classes("items-center gap-3 px-6 py-3 shadow-md"):
            ui.icon("qr_code_2", size="32px")
            ui.label(settings.APP_TITLE).classes("text-h6 text-weight-bold")
            ui.label("Control de asistencia y registro de eventos").classes(
                "text-caption opacity-80"
            )

        with ui.column().classes("w-full max-w-6xl mx-auto p-4 gap-4"):
            with ui.tabs().classes("w-full") as tabs:
                ui.tab("events", label="Eventos", icon="event")
                ui.tab("register", label="Inscripción", icon="person_add")
                ui.tab("checkin", label="Check-in", icon="qr_code_scanner")
                ui.tab("reports", label="Reportes", icon="table_view")

            with ui.tab_panels(tabs, value="events").classes("w-full bg-transparent"):
                with ui.tab_panel("events"):
                    self._build_events_tab()
                with ui.tab_panel("register"):
                    self._build_register_tab()
                with ui.tab_panel("checkin"):
                    focus_scanner, start_camera, stop_camera = self._build_checkin_tab()
                with ui.tab_panel("reports"):
                    self._build_reports_tab()

        def on_tab_change(e) -> None:
            if e.value == "checkin":
                ui.timer(0.3, focus_scanner, once=True)
                ui.timer(0.4, start_camera, once=True)  # abre la cámara en vivo al entrar
            else:
                stop_camera()

        tabs.on_value_change(on_tab_change)

    # ------------------------------------------------------ 1. Gestión eventos
    def _build_events_tab(self) -> None:
        with ui.row().classes("w-full items-start gap-6"):
            with ui.card().classes("w-full md:w-96"):
                ui.label("Nuevo evento").classes("text-h6")
                name = ui.input("Nombre *").props("outlined dense").classes("w-full")
                description = (
                    ui.textarea("Descripción").props("outlined dense rows=3").classes("w-full")
                )
                location = ui.input("Lugar").props("outlined dense").classes("w-full")
                start = (
                    ui.input("Fecha de inicio *", value=date.today().isoformat())
                    .props("outlined dense type=date")
                    .classes("w-full")
                )

                def create() -> None:
                    try:
                        event_service.create_event(
                            name.value, description.value, location.value, start.value
                        )
                    except ValidationError as exc:
                        ui.notify(str(exc), type="warning")
                        return
                    ui.notify("Evento creado correctamente.", type="positive")
                    name.value = ""
                    description.value = ""
                    location.value = ""
                    self._refresh_events_table()
                    self._refresh_event_selects()

                ui.button("Crear evento", icon="add", on_click=create).classes("w-full")

            with ui.card().classes("flex-1 min-w-[320px]"):
                ui.label("Eventos registrados").classes("text-h6")
                columns = [
                    {"name": "id", "label": "ID", "field": "id", "align": "left"},
                    {"name": "name", "label": "Evento", "field": "name", "align": "left", "sortable": True},
                    {"name": "location", "label": "Lugar", "field": "location", "align": "left"},
                    {"name": "start_date", "label": "Fecha", "field": "start_date", "align": "left"},
                    {"name": "participants", "label": "Inscritos", "field": "participants", "align": "right"},
                ]
                self._events_table = ui.table(
                    columns=columns,
                    rows=event_service.list_event_summaries(),
                    row_key="id",
                    selection="single",
                ).classes("w-full")

                pending: dict[str, int | None] = {"id": None}
                with ui.dialog() as dialog, ui.card():
                    confirm_label = ui.label()
                    with ui.row().classes("justify-end w-full"):
                        ui.button("Cancelar", on_click=dialog.close).props("flat")

                        def confirm_delete() -> None:
                            if pending["id"] is not None:
                                event_service.delete_event(pending["id"])
                                ui.notify("Evento eliminado.", type="info")
                                self._refresh_events_table()
                                self._refresh_event_selects()
                            dialog.close()

                        ui.button("Eliminar", color="negative", on_click=confirm_delete)

                def ask_delete() -> None:
                    selected = self._events_table.selected
                    if not selected:
                        ui.notify("Seleccione un evento de la tabla.", type="warning")
                        return
                    row = selected[0]
                    pending["id"] = row["id"]
                    confirm_label.set_text(
                        f"¿Eliminar «{row['name']}» junto con sus {row['participants']} "
                        "inscritos y todas sus asistencias? Esta acción no se puede deshacer."
                    )
                    dialog.open()

                with ui.row().classes("gap-2"):
                    ui.button("Eliminar seleccionado", icon="delete", color="negative", on_click=ask_delete).props("outline")
                    ui.button("Actualizar", icon="refresh", on_click=self._refresh_events_table).props("flat")

    # ----------------------------------------------------------- 2. Inscripción
    def _build_register_tab(self) -> None:
        with ui.row().classes("w-full items-start gap-6"):
            with ui.card().classes("w-full md:w-96"):
                ui.label("Inscribir participante").classes("text-h6")
                event_select = self._new_event_select("Evento *")
                full_name = ui.input("Nombre completo *").props("outlined dense").classes("w-full")
                email = ui.input("Correo electrónico *").props("outlined dense type=email").classes("w-full")
                organization = ui.input("Organización").props("outlined dense").classes("w-full")
                ui.button(
                    "Inscribir y generar QR", icon="qr_code_2", on_click=lambda: register()
                ).classes("w-full")

            with ui.card().classes("w-full md:w-80 items-center"):
                ui.label("Credencial QR").classes("text-h6")
                preview = ui.column().classes("items-center gap-2 w-full")
                with preview:
                    ui.label("El código aparecerá aquí al inscribir a un participante.").classes("text-grey text-center")

        with ui.card().classes("w-full"):
            ui.label("Participantes del evento").classes("text-h6")
            columns = [
                {"name": "full_name", "label": "Nombre", "field": "full_name", "align": "left", "sortable": True},
                {"name": "email", "label": "Correo", "field": "email", "align": "left"},
                {"name": "organization", "label": "Organización", "field": "organization", "align": "left"},
                {"name": "registered_at", "label": "Inscrito", "field": "registered_at", "align": "left"},
            ]
            table = ui.table(columns=columns, rows=[], row_key="id", selection="single", pagination=10).classes("w-full")
            ui.button(
                "Ver QR del seleccionado", icon="visibility", on_click=lambda: show_selected_qr()
            ).props("outline")

        def show_qr(name: str, token: str) -> None:
            preview.clear()
            data_uri = qr_service.generate_qr_base64(token)
            with preview:
                ui.label(name).classes("text-subtitle1 text-weight-bold text-center")
                ui.image(data_uri).classes("w-64 h-64")
                ui.label(token).classes("text-xs text-grey break-all text-center")

                def download() -> None:
                    ui.download(
                        qr_service.generate_qr_png_bytes(token),
                        filename=f"qr_{_slug(name)}.png",
                        media_type="image/png",
                    )

                ui.button("Descargar PNG", icon="download", on_click=download).props("outline")

        def participant_rows() -> list[dict]:
            if not event_select.value:
                return []
            return [
                {
                    "id": p.id,
                    "full_name": p.full_name,
                    "email": p.email,
                    "organization": p.organization or "—",
                    "registered_at": f"{p.registered_at:%d/%m/%Y %H:%M}",
                    "token": str(p.qr_token),
                }
                for p in event_service.list_participants(event_select.value)
            ]

        def refresh_participants() -> None:
            table.update_rows(participant_rows())

        self._refresh_participants = refresh_participants
        event_select.on_value_change(lambda _: refresh_participants())

        def register() -> None:
            try:
                participant = event_service.register_participant(
                    event_select.value, full_name.value, email.value, organization.value
                )
            except ValidationError as exc:
                ui.notify(str(exc), type="warning")
                return
            ui.notify(f"{participant.full_name} inscrito correctamente.", type="positive")
            show_qr(participant.full_name, str(participant.qr_token))
            full_name.value = ""
            email.value = ""
            organization.value = ""
            refresh_participants()
            self._refresh_events_table()

        def show_selected_qr() -> None:
            if not table.selected:
                ui.notify("Seleccione un participante de la tabla.", type="warning")
                return
            row = table.selected[0]
            show_qr(row["full_name"], row["token"])


    # ------------------------------------------------------------ 3. Check-in
    def _build_checkin_tab(self):
        history: list[dict] = []
        counter = {"n": 0}
        camera = {"on": False, "busy": False, "token": 0}

        with ui.card().classes("w-full items-center p-6 gap-3"):
            ui.icon("qr_code_scanner", size="64px").classes("text-primary")
            ui.label("Terminal de Check-in").classes("text-h5")
            ui.label(
                "Apunte el QR a la cámara en vivo, use un lector USB "
                "(envía Enter automáticamente) o pegue el token y pulse Enter."
            ).classes("text-grey text-center")

            with ui.element("div").classes("relative w-full max-w-xl rounded-xl overflow-hidden bg-black").style(
                "min-height: 300px"
            ):
                ui.html('<div id="qr-reader"></div>')
                placeholder = ui.column().classes(
                    "absolute-center items-center text-white text-center gap-1 p-4"
                )
                with placeholder:
                    ui.icon("videocam_off", size="48px")
                    status_lbl = ui.label("Cámara detenida")

            with ui.row().classes("items-center justify-center gap-3"):
                camera_btn = ui.button("Activar cámara", icon="photo_camera")
                facing = ui.toggle({"environment": "Trasera", "user": "Frontal"}, value="environment")

            scan = (
                ui.input(placeholder="Lector USB / pegar token y Enter")
                .props("outlined autofocus autocomplete=off input-class=text-center")
                .classes("w-full max-w-xl text-h6")
            )
            result_box = ui.column().classes("w-full max-w-xl items-stretch")

        with ui.card().classes("w-full"):
            ui.label("Últimas lecturas").classes("text-h6")
            columns = [
                {"name": "time", "label": "Hora", "field": "time", "align": "left"},
                {"name": "who", "label": "Participante", "field": "who", "align": "left"},
                {"name": "status", "label": "Resultado", "field": "status", "align": "left"},
            ]
            history_table = ui.table(columns=columns, rows=[], row_key="id").classes("w-full")

        def focus_scanner() -> None:
            # En pantallas táctiles no se enfoca el campo para no abrir el teclado sobre la cámara.
            ui.run_javascript(
                "if (!window.matchMedia('(pointer: coarse)').matches) getElement(%d).focus()" % scan.id
            )

        def process_token(raw: str) -> None:
            raw = (raw or "").strip()
            if not raw:
                return
            result = checkin_service.process_check_in(raw)
            classes, icon, title = STATUS_STYLES[result.status]

            result_box.clear()
            with result_box:
                with ui.card().classes(f"w-full items-center p-4 {classes}"):
                    ui.icon(icon, size="56px")
                    ui.label(title).classes("text-h6 text-weight-bold")
                    if result.participant_name:
                        ui.label(result.participant_name).classes("text-h5 text-center")
                    if result.event_name:
                        ui.label(result.event_name).classes("text-subtitle2 text-center")
                    ui.label(result.message).classes("text-center")
                    if result.check_in_time:
                        ui.label(f"Hora: {result.check_in_time:%H:%M:%S}").classes("text-caption")

            ui.run_javascript(
                "navigator.vibrate && navigator.vibrate(%s)"
                % ("[120]" if result.ok else "[80,60,80]")
            )

            counter["n"] += 1
            history.insert(
                0,
                {
                    "id": counter["n"],
                    "time": datetime.now().strftime("%H:%M:%S"),
                    "who": result.participant_name or raw[:36],
                    "status": title.capitalize(),
                },
            )
            del history[10:]
            history_table.update_rows(list(history))

        def handle_scan() -> None:
            raw = scan.value or ""
            scan.value = ""
            focus_scanner()
            process_token(raw)

        scan.on("keydown.enter", handle_scan)
        ui.on("qr_scanned", lambda e: process_token((e.args or {}).get("text", "")))

        def set_camera_ui(active: bool) -> None:
            camera["on"] = active
            placeholder.set_visibility(not active)
            camera_btn.set_text("Detener cámara" if active else "Activar cámara")
            camera_btn.props("icon=stop color=negative" if active else "icon=photo_camera color=primary")

        async def start_camera() -> None:
            if camera["on"] or camera["busy"]:
                return
            camera["busy"] = True
            camera["token"] += 1
            token = camera["token"]
            status_lbl.set_text("Iniciando cámara…")
            try:
                status = await ui.run_javascript(f"eqrStart('{facing.value}')", timeout=60)
            except TimeoutError:
                status = "error:La cámara tardó demasiado en responder."
            finally:
                camera["busy"] = False

            if token != camera["token"]:
                # Se pidió detener (o se cambió de pestaña) mientras arrancaba.
                ui.run_javascript("eqrStop()")
                set_camera_ui(False)
                status_lbl.set_text("Cámara detenida")
                return
            if status == "ok":
                set_camera_ui(True)
                return

            set_camera_ui(False)
            if status == "insecure":
                message = "La cámara requiere una conexión segura (HTTPS)."
            else:
                detail = (status or "").removeprefix("error:")
                message = f"No se pudo iniciar la cámara: {detail}"
            status_lbl.set_text(message + " Pulse «Activar cámara» para reintentar.")
            ui.notify(message, type="negative", multi_line=True)

        def stop_camera() -> None:
            camera["token"] += 1
            if camera["on"]:
                ui.run_javascript("eqrStop()")
                set_camera_ui(False)
                status_lbl.set_text("Cámara detenida")

        async def toggle_camera() -> None:
            if camera["on"] or camera["busy"]:
                stop_camera()
            else:
                await start_camera()

        async def change_facing() -> None:
            if camera["on"]:
                stop_camera()
                await ui.run_javascript("eqrStop()", timeout=10)
                await start_camera()

        camera_btn.on_click(toggle_camera)
        facing.on_value_change(change_facing)
        return focus_scanner, start_camera, stop_camera

    # ------------------------------------------------------------ 4. Reportes
    def _build_reports_tab(self) -> None:
        with ui.card().classes("w-full"):
            ui.label("Reporte de asistencia").classes("text-h6")
            with ui.row().classes("w-full items-center gap-4"):
                event_select = self._new_event_select("Evento")
                event_select.classes(remove="w-full", add="flex-1 min-w-[260px]")
                date_filter = (
                    ui.input("Filtrar por fecha (opcional)")
                    .props("outlined dense clearable type=date")
                    .classes("w-56")
                )

            with ui.row().classes("gap-6"):
                registered_lbl = ui.label("Inscritos: —")
                unique_lbl = ui.label("Asistentes únicos: —")
                records_lbl = ui.label("Registros de asistencia: —")

            columns = [
                {"name": "date", "label": "Fecha", "field": "date", "align": "left", "sortable": True},
                {"name": "time", "label": "Hora", "field": "time", "align": "left", "sortable": True},
                {"name": "full_name", "label": "Participante", "field": "full_name", "align": "left", "sortable": True},
                {"name": "email", "label": "Correo", "field": "email", "align": "left"},
                {"name": "organization", "label": "Organización", "field": "organization", "align": "left"},
                {"name": "notes", "label": "Notas", "field": "notes", "align": "left"},
            ]
            table = ui.table(columns=columns, rows=[], row_key="id", pagination=15).classes("w-full")

            def load(warn: bool = True) -> None:
                if not event_select.value:
                    table.update_rows([])
                    registered_lbl.set_text("Inscritos: —")
                    unique_lbl.set_text("Asistentes únicos: —")
                    records_lbl.set_text("Registros de asistencia: —")
                    if warn:
                        ui.notify("Seleccione un evento.", type="warning")
                    return
                day = _parse_date(date_filter.value)
                table.update_rows(export_service.get_attendance_rows(event_select.value, day))
                summary = export_service.get_summary(event_select.value, day)
                registered_lbl.set_text(f"Inscritos: {summary['registered']}")
                unique_lbl.set_text(f"Asistentes únicos: {summary['unique']}")
                records_lbl.set_text(f"Registros de asistencia: {summary['records']}")

            def download_csv() -> None:
                if not event_select.value:
                    ui.notify("Seleccione un evento.", type="warning")
                    return
                event = event_service.get_event(event_select.value)
                if event is None:
                    ui.notify("El evento ya no existe.", type="negative")
                    return
                day = _parse_date(date_filter.value)
                ui.download(
                    export_service.export_attendance_csv(event.id, day),
                    filename=export_service.build_filename(event.name),
                    media_type="text/csv",
                )

            event_select.on_value_change(lambda _: load(warn=False))
            date_filter.on_value_change(lambda _: load(warn=False))

            with ui.row().classes("gap-2"):
                ui.button("Actualizar", icon="refresh", on_click=lambda: load(warn=True)).props("outline")
                ui.button("Descargar CSV", icon="download", on_click=download_csv)


def register_pages() -> None:
    app.add_static_files("/libs", STATIC_DIR)

    @ui.page("/")
    def index() -> None:
        EventQRPage().build()
