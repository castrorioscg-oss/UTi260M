"""Textos de la interfaz en inglés / español."""

LANGS = {"en": "English", "es": "Español"}
_lang = "en"

S = {
    # ventana y menús
    "title": ("UTi260M Thermal Viewer", "Visor Térmico UTi260M"),
    "m_file": ("&File", "&Archivo"),
    "m_snapshot": ("Snapshot", "Foto"),
    "m_open": ("Open capture…", "Abrir captura…"),
    "m_folder": ("Open captures folder", "Abrir carpeta de capturas"),
    "m_exit": ("Exit", "Salir"),
    "m_lang": ("&Language", "&Idioma"),
    # secciones
    "sec_capture": ("Capture", "Captura"),
    "sec_image": ("Image", "Imagen"),
    "sec_range": ("Temperature range (°C)", "Rango de temperatura (°C)"),
    "sec_material": ("Material / Emissivity", "Material / Emisividad"),
    "sec_meas": ("Measurements", "Mediciones"),
    "sec_alarm": ("Alarm", "Alarma"),
    "sec_compare": ("PCB comparison (differential)", "Comparación PCB (diferencial)"),
    # captura
    "photo": ("📷 Snapshot  [Space]", "📷 Foto  [Espacio]"),
    "rec": ("⏺ Record video  [R]", "⏺ Grabar video  [R]"),
    "rec_stop": ("⏹ Stop  [R]", "⏹ Detener  [R]"),
    "freeze": ("❄ Freeze  [F]", "❄ Congelar  [F]"),
    "open": ("Open capture…", "Abrir captura…"),
    "folder": ("Folder…", "Carpeta…"),
    "show_folder": ("Show folder", "Ver carpeta"),
    # imagen
    "palette": ("Palette", "Paleta"),
    "unit": ("Unit", "Unidad"),
    "smooth": ("Smooth image", "Imagen suavizada"),
    "hd": ("HD", "HD"),
    "hd_tip": ("Image enhancement: denoise + 4x upscaling + detail enhancement.\n"
               "Display only: measurements always use the real sensor data.",
               "Mejora de imagen: reducción de ruido + ampliación 4x + realce de detalle.\n"
               "Solo visual: las mediciones siempre usan los datos reales del sensor."),
    "hd_0": ("Off", "Apagado"), "hd_1": ("Low", "Bajo"), "hd_2": ("Medium", "Medio"), "hd_3": ("High", "Alto"),
    "avg": ("Averaging", "Promedio"),
    "frames": ("frames", "cuadros"),
    "avg_tip": ("Averages N frames to reduce noise (useful for small differences)",
                "Promedia N cuadros para reducir ruido (útil en diferencias pequeñas)"),
    "rotate": ("Rotate 90°", "Rotar 90°"),
    "mirror_h": ("Mirror H", "Espejo H"),
    "mirror_v": ("Mirror V", "Espejo V"),
    # rango
    "auto": ("Automatic", "Automático"),
    "manual": ("Manual", "Manual"),
    "lock": ("Lock current", "Fijar actual"),
    "lock_tip": ("Switch to manual using the range currently shown",
                 "Pasa a manual con el rango que se está mostrando"),
    "min": ("Min", "Mín"),
    "max": ("Max", "Máx"),
    "avg_s": ("Avg", "Prom"),
    "center": ("Center", "Centro"),
    # material
    "eps": ("Emissivity ε", "Emisividad ε"),
    "trefl": ("Reflected T.", "T. reflejada"),
    "trefl_tip": ("Reflected (ambient) temperature. Matters for low-emissivity materials.",
                  "Temperatura reflejada (ambiente). Importa en materiales de baja emisividad."),
    "metal_hint": ("Shiny metals (solder, copper) read wrong: cover the spot with Kapton tape "
                   "or matte paint and use ε 0.95.",
                   "Metales brillantes (estaño, cobre) miden mal: cubre el punto con cinta Kapton "
                   "o pintura mate y usa ε 0.95."),
    # mediciones
    "clear": ("Clear [Del]", "Borrar [Supr]"),
    "meas_hint": ("Click: point · Drag: rectangle · Right-click: delete",
                  "Clic: punto · Arrastrar: rectángulo · Clic der.: borrar"),
    "col_val": ("Max / Value", "Máx / Valor"),
    # alarma
    "a_hi": ("High >", "Alta >"),
    "a_lo": ("Low <", "Baja <"),
    "sound": ("Sound", "Sonido"),
    "green": ("■ green", "■ verde"),
    "cyan": ("■ cyan", "■ cian"),
    "alarm": ("⚠ ALARM", "⚠ ALARMA"),
    "a_high": ("HIGH", "ALTA"),
    "a_low": ("LOW", "BAJA"),
    # diferencial
    "take_ref": ("Take reference", "Tomar referencia"),
    "take_ref_tip": ("Averages 16 frames of the GOOD board in the same position",
                     "Promedia 16 cuadros de la tarjeta BUENA en la misma posición"),
    "taking_ref": ("Taking reference… {n}/16", "Tomando referencia… {n}/16"),
    "load_ref": ("Load ref…", "Cargar ref…"),
    "save_ref": ("Save ref…", "Guardar ref…"),
    "show_diff": ("Show difference [D]", "Mostrar diferencia [D]"),
    "auto_scale": ("Auto scale", "Escala auto"),
    "no_ref": ("No reference", "Sin referencia"),
    "ref_is": ("Reference: {d}", "Referencia: {d}"),
    "ref_captured": ("captured {t}", "capturada {t}"),
    "file_ref": ("{n}", "{n}"),
    "ref_frozen":("from frozen image", "desde imagen congelada"),
    "diff_info": ("Red = hotter than the good board; blue = colder.",
                  "Rojo = más caliente que la tarjeta buena; azul = más frío."),
    "diff_title": ("Differential", "Diferencial"),
    "diff_need": ("First take or load a reference from a known-good board.",
                  "Primero toma o carga una referencia de una tarjeta en buen estado."),
    "ref_title": ("Reference", "Referencia"),
    "ref_none": ("There is no reference to save.", "No hay referencia para guardar."),
    "ref_filter": ("Reference or capture (*.npz)", "Referencia o captura (*.npz)"),
    # estado
    "st_search": ("Searching for UTi260M camera…", "Buscando cámara UTi260M…"),
    "st_notfound": ("Camera not found. Retrying…", "Cámara no encontrada. Reintentando…"),
    "st_conn": ("Connected (device {i})", "Conectada (dispositivo {i})"),
    "st_lost": ("Connection lost. Reconnecting…", "Conexión perdida. Reconectando…"),
    "st_demo": ("DEMO MODE (no camera)", "MODO DEMO (sin cámara)"),
    "frozen": ("FROZEN", "CONGELADO"),
    "file": ("file", "archivo"),
    "recording": ("⏺ RECORDING", "⏺ GRABANDO"),
    "waiting": ("Waiting for camera image…", "Esperando imagen de la cámara…"),
    # archivos
    "saved": ("Capture saved: {n}.png (+ .npz and .csv data)", "Captura guardada: {n}.png (+ datos .npz y .csv)"),
    "video": ("Video", "Video"),
    "video_fail": ("Could not create the video file.", "No se pudo crear el archivo de video."),
    "video_saved": ("Video saved: {n}", "Video guardado: {n}"),
    "dlg_folder": ("Captures folder", "Carpeta de capturas"),
    "dlg_open": ("Open capture", "Abrir captura"),
    "open_filter": ("UTi260M data (*_data.npz *_datos.npz)", "Datos UTi260M (*_data.npz *_datos.npz)"),
    "read_fail": ("Could not read the file:\n{e}", "No se pudo leer el archivo:\n{e}"),
    "t_refl_s": ("Refl.T", "T.refl"),
    "diff_mode": ("DIFFERENTIAL MODE", "MODO DIFERENCIAL"),
    "roi_max": ("max", "máx"),
    "roi_avg": ("avg", "prom"),
    # materiales
    "mat_custom": ("Custom", "Personalizado"),
    "mat_mask": ("Solder mask (green/black)", "Máscara de soldadura (verde/negra)"),
    "mat_fr4": ("Bare FR4", "FR4 sin máscara"),
    "mat_ic": ("Plastic IC package / epoxy", "Encapsulado plástico IC / epoxi"),
    "mat_kapton": ("Kapton / electrical tape", "Cinta Kapton / cinta aislante"),
    "mat_paint": ("Matte black paint", "Pintura mate negra"),
    "mat_ceramic": ("Ceramic (MLCC capacitors)", "Cerámica (capacitores MLCC)"),
    "mat_silicone": ("Silicone / thermal paste", "Silicona / pasta térmica"),
    "mat_anod": ("Anodized aluminum heatsink", "Disipador aluminio anodizado"),
    "mat_cu_ox": ("Oxidized copper", "Cobre oxidado"),
    "mat_al": ("Untreated aluminum", "Aluminio sin tratar"),
    "mat_solder": ("Shiny solder / tin", "Soldadura / estaño brillante"),
    "mat_cu_pol": ("Polished copper", "Cobre pulido"),
    "mat_skin": ("Human skin", "Piel humana"),
    "mat_bb": ("Blackbody / reference", "Cuerpo negro / referencia"),
    # paletas
    "pal_iron": ("Iron", "Hierro"),
    "pal_rainbow": ("Rainbow", "Arcoíris"),
    "pal_rainbow_hc": ("Rainbow HC", "Arcoíris HC"),
    "pal_white_hot": ("White hot", "Blanco caliente"),
    "pal_black_hot": ("Black hot", "Negro caliente"),
    "pal_lava": ("Lava", "Lava"),
    "pal_magma": ("Magma", "Magma"),
    "pal_red_hot": ("Red hot", "Rojo caliente"),
}


def set_lang(lang):
    global _lang
    _lang = lang if lang in LANGS else "en"


def lang():
    return _lang


def tr(key, **kw):
    en, es = S.get(key, (key, key))
    s = es if _lang == "es" else en
    return s.format(**kw) if kw else s
