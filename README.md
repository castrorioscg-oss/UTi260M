# Visor Térmico UTi260M (Windows)

Software para usar la cámara termográfica UNI-T UTi260M (USB `VID_0BDA&PID_5830`) en el PC,
orientado a diagnóstico de tarjetas PCB.

## Descarga (sin instalar Python)
En [Releases](https://github.com/castrorioscg-oss/UTi260M/releases/latest) descarga `UTi260M-windows.zip`,
descomprímelo y ejecuta `UTi260M.exe`. Funciona en Windows 10 y 11 (64 bits). La cámara se reconoce como
cámara USB estándar, así que no necesita driver.

## Ejecutar desde el código
- Doble clic en **`Ejecutar.bat`** (instala dependencias la primera vez).
- O bien: `python main.py` · `python main.py --demo` (sin cámara) · `python main.py --index 1`
- Para un `.exe` portable: `build_exe.bat` → `dist\UTi260M\UTi260M.exe`

Cierra cualquier otra app que esté usando la cámara antes de abrir el visor.

## Controles
| Acción | Cómo |
|---|---|
| Foto (PNG + `_data.npz` + `_temps.csv`) | `Espacio` o botón Foto |
| Grabar video MP4 | `R` |
| Congelar imagen | `F` |
| Punto de medición | clic izquierdo |
| Rectángulo (máx/mín/prom) | arrastrar |
| Borrar medición | clic derecho sobre ella · `Supr` borra todas |
| Modo diferencial | `D` |

- **Idioma:** menú *Language / Idioma* (inglés por defecto, español opcional).
- **Panel lateral:** secciones desplegables; el programa recuerda cuáles dejaste abiertas.
- **Al abrir:** paleta Lava, rango automático y alarmas apagadas, sin importar cómo se cerró la sesión anterior.
- **Paletas:** Lava, Hierro, Arcoíris, Arcoíris HC, Blanco/Negro caliente, Magma, Rojo caliente.
- **HD (Apagado/Bajo/Medio/Alto):** reduce el ruido (filtro bilateral), amplía 4x (Lanczos) y realza el detalle (tipo DDE).
  Es solo visual: el sensor sigue siendo de 256×192 y **todas las mediciones usan los datos reales**.
- **Rango:** automático o manual; "Fijar actual" congela la escala para comparar tarjetas.
- **Emisividad:** presets por material, o un valor manual, más la temperatura reflejada.
- **Alarma:** pinta de verde (alta) o cian (baja) los píxeles fuera del umbral, con sonido opcional.
- **Promedio de cuadros:** reduce el ruido (±0.1–0.2 °C) para ver diferencias pequeñas.
- **Abrir captura:** reabre un `_data.npz` (o `_datos.npz` de versiones anteriores) para analizarlo después. Puedes cambiar la emisividad, la paleta
  y las mediciones sobre la imagen guardada.

## Flujo recomendado para PCB
1. Fija la cámara en un soporte, a una distancia fija de la tarjeta (mínimo ~10–15 cm para que enfoque).
2. Energiza una **tarjeta buena** y espera a que se estabilice térmicamente → **Tomar referencia** → **Guardar ref…**
3. Pon la **tarjeta con falla** en la misma posición y con las mismas condiciones → activa **Mostrar diferencia**.
   Rojo = más caliente que la buena (cortos, componentes con fuga); azul = más frío (componentes que no trabajan).
4. Para buscar cortos en rieles, inyecta una corriente limitada y busca el punto máximo.

## Notas técnicas
- La cámara mide en la banda de 8–14 µm, que es fija. Lo que se ajusta según el material es la **emisividad**.
- Las superficies brillantes (estaño, cobre, aluminio) reflejan el entorno y dan lecturas falsas.
  Cubre el punto con cinta Kapton o pintura mate y usa ε ≈ 0.95.
- La corrección de emisividad usa una aproximación de Stefan-Boltzmann (T⁴). Si ves un desvío sistemático
  contra un termómetro de contacto, ajusta `EPS_DEVICE` en `uti260m/processing.py`.
- La calibración de shutter (el "clic" de la cámara) la hace la cámara automáticamente.
- CSV: en español usa `;` y coma decimal (Excel en español); en inglés usa `,` y punto decimal.
