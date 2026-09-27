/**
 * Lote de claves p.extras.* para las páginas nuevas:
 * ExternalCalendarsPage (cal.*) y WhiteboardsPage (wb.*).
 *
 * Se mergea en index.ts dentro de `batches` (pendiente de wiring por el
 * propietario de index.ts).
 */
export default {
  es: {
    // ExternalCalendarsPage
    "p.extras.cal.title": "Calendarios externos",
    "p.extras.cal.desc":
      "Suscribe feeds iCal (ICS) y superpón sus eventos en el calendario de tareas.",
    "p.extras.cal.new": "Añadir calendario",
    "p.extras.cal.name": "Nombre",
    "p.extras.cal.url": "URL del feed ICS",
    "p.extras.cal.urlHint": "Pega la URL de suscripción del calendario (.ics).",
    "p.extras.cal.emptyTitle": "Sin calendarios externos",
    "p.extras.cal.emptyDesc":
      "Añade una suscripción iCal para ver sus eventos junto a tus tareas.",
    "p.extras.cal.created": "Calendario añadido",
    "p.extras.cal.createError": "No se pudo añadir el calendario. Revisa la URL.",
    "p.extras.cal.deleted": "Calendario eliminado",
    "p.extras.cal.deleteError": "No se pudo eliminar el calendario",
    "p.extras.cal.confirmDelete":
      "¿Eliminar este calendario externo? Sus eventos dejarán de mostrarse.",
    "p.extras.cal.refresh": "Sincronizar ahora",
    "p.extras.cal.refreshed": "Calendario sincronizado",
    "p.extras.cal.refreshError": "No se pudo sincronizar el calendario",
    "p.extras.cal.updateError": "No se pudo actualizar el calendario",
    "p.extras.cal.active": "Activo",
    "p.extras.cal.neverSynced": "Nunca sincronizado",
    "p.extras.cal.lastSynced": "Última sincronización",
    "p.extras.cal.syncError": "Error de sincronización",
    "p.extras.cal.refreshAria": "Sincronizar calendario",
    "p.extras.cal.deleteAria": "Eliminar calendario",

    // WhiteboardsPage - lista
    "p.extras.wb.title": "Pizarras",
    "p.extras.wb.desc": "Lienzos por proyecto para notas visuales y conexiones.",
    "p.extras.wb.new": "Nueva pizarra",
    "p.extras.wb.name": "Nombre",
    "p.extras.wb.project": "Proyecto",
    "p.extras.wb.emptyTitle": "Sin pizarras",
    "p.extras.wb.emptyDesc":
      "Crea una pizarra para organizar notas visuales de tu proyecto.",
    "p.extras.wb.created": "Pizarra creada",
    "p.extras.wb.createError": "No se pudo crear la pizarra",
    "p.extras.wb.deleted": "Pizarra eliminada",
    "p.extras.wb.deleteError": "No se pudo eliminar la pizarra",
    "p.extras.wb.confirmDelete": "¿Eliminar esta pizarra? Se perderá su contenido.",
    "p.extras.wb.deleteAria": "Eliminar pizarra",
    "p.extras.wb.updated": "Actualizada {{date}}",
    // WhiteboardsPage - detalle
    "p.extras.wb.back": "Volver a pizarras",
    "p.extras.wb.addNote": "Añadir nota",
    "p.extras.wb.connect": "Conectar",
    "p.extras.wb.connectActive": "Conectando…",
    "p.extras.wb.connectHint":
      "Toca dos notas para unirlas. Toca una línea para borrarla.",
    "p.extras.wb.notePlaceholder": "Escribe aquí…",
    "p.extras.wb.noteDeleteAria": "Eliminar nota",
    "p.extras.wb.saving": "Guardando…",
    "p.extras.wb.saved": "Guardado",
    "p.extras.wb.saveError": "No se pudo guardar la pizarra",
    "p.extras.wb.loadError": "No se pudo cargar la pizarra",
    "p.extras.wb.notFound": "Pizarra no encontrada",
    "p.extras.wb.retry": "Reintentar",
  },
  en: {
    // ExternalCalendarsPage
    "p.extras.cal.title": "External calendars",
    "p.extras.cal.desc":
      "Subscribe iCal (ICS) feeds and overlay their events on the task calendar.",
    "p.extras.cal.new": "Add calendar",
    "p.extras.cal.name": "Name",
    "p.extras.cal.url": "ICS feed URL",
    "p.extras.cal.urlHint": "Paste the calendar subscription URL (.ics).",
    "p.extras.cal.emptyTitle": "No external calendars",
    "p.extras.cal.emptyDesc":
      "Add an iCal subscription to see its events next to your tasks.",
    "p.extras.cal.created": "Calendar added",
    "p.extras.cal.createError": "Could not add the calendar. Check the URL.",
    "p.extras.cal.deleted": "Calendar deleted",
    "p.extras.cal.deleteError": "Could not delete the calendar",
    "p.extras.cal.confirmDelete":
      "Delete this external calendar? Its events will stop showing.",
    "p.extras.cal.refresh": "Sync now",
    "p.extras.cal.refreshed": "Calendar synced",
    "p.extras.cal.refreshError": "Could not sync the calendar",
    "p.extras.cal.updateError": "Could not update the calendar",
    "p.extras.cal.active": "Active",
    "p.extras.cal.neverSynced": "Never synced",
    "p.extras.cal.lastSynced": "Last synced",
    "p.extras.cal.syncError": "Sync error",
    "p.extras.cal.refreshAria": "Sync calendar",
    "p.extras.cal.deleteAria": "Delete calendar",

    // WhiteboardsPage - list
    "p.extras.wb.title": "Whiteboards",
    "p.extras.wb.desc": "Per-project canvases for visual notes and connections.",
    "p.extras.wb.new": "New whiteboard",
    "p.extras.wb.name": "Name",
    "p.extras.wb.project": "Project",
    "p.extras.wb.emptyTitle": "No whiteboards",
    "p.extras.wb.emptyDesc":
      "Create a whiteboard to organize visual notes for your project.",
    "p.extras.wb.created": "Whiteboard created",
    "p.extras.wb.createError": "Could not create the whiteboard",
    "p.extras.wb.deleted": "Whiteboard deleted",
    "p.extras.wb.deleteError": "Could not delete the whiteboard",
    "p.extras.wb.confirmDelete": "Delete this whiteboard? Its content will be lost.",
    "p.extras.wb.deleteAria": "Delete whiteboard",
    "p.extras.wb.updated": "Updated {{date}}",
    // WhiteboardsPage - detail
    "p.extras.wb.back": "Back to whiteboards",
    "p.extras.wb.addNote": "Add note",
    "p.extras.wb.connect": "Connect",
    "p.extras.wb.connectActive": "Connecting…",
    "p.extras.wb.connectHint": "Tap two notes to link them. Tap a line to delete it.",
    "p.extras.wb.notePlaceholder": "Type here…",
    "p.extras.wb.noteDeleteAria": "Delete note",
    "p.extras.wb.saving": "Saving…",
    "p.extras.wb.saved": "Saved",
    "p.extras.wb.saveError": "Could not save the whiteboard",
    "p.extras.wb.loadError": "Could not load the whiteboard",
    "p.extras.wb.notFound": "Whiteboard not found",
    "p.extras.wb.retry": "Retry",
  },
};
