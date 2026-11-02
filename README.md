# PrisDrop

Descargador de videos y música de YouTube con interfaz estilo YouTube, reproductor multimedia
integrado y accesos directos a páginas web. Usa **yt-dlp**, **FFmpeg** y **Deno** (se descargan solos).

## Ejecutar

```bash
pip install -r requirements.txt
pythonw main.py
```

En Windows también puedes abrir `main.py` directamente: la consola se oculta al iniciarse desde el Explorador.
Si lo ejecutas desde una terminal ya abierta, esta se mantiene visible. Requiere Python 3.10+.
La primera vez descarga yt-dlp, FFmpeg (~100 MB) y Deno a
`%APPDATA%\PrisDrop\bin`. Si ya tenías Descargatube instalado, la carpeta de datos se migra
automáticamente a PrisDrop al iniciar.

## Novedades de la V2

- **Pantalla completa propia**: se abre con el botón de pantalla completa para videos y música, o con doble clic en el video.
  En audio muestra la carátula y un visualizador que responde al nivel del sonido. Los controles aparecen al mover el cursor y se
  ocultan a los 2,5 s. **Esc** (o F, o doble clic) sale. Espacio = pausa,
  ←/→ = ±5 s, ↑/↓ = volumen. Los videos verticales (Shorts) se ven con barras negras laterales.
- **Barra de reproducción**: puedes hacer clic en cualquier punto de la línea para saltar a esa posición
  y arrastrar desde ahí; también puedes seguir arrastrando el control circular.
- **Integración multimedia de Windows**: el reproductor publica título, artista o subtítulo y carátula
  en los controles multimedia del sistema. Desde ellos puedes reproducir, pausar, detener y cambiar
  de elemento. El visualizador de audio a pantalla completa refleja los niveles del audio decodificado.
- **Avisos legales**: el botón ❕ de la barra inferior muestra la licencia del proyecto, las licencias
  de terceros y el aviso legal. Consulta también [LEGAL_CHECKLIST.md](./LEGAL_CHECKLIST.md).
- **Cola minimizable**: oculta o vuelve a mostrar la cola desde el reproductor.
- **Metadatos y carátulas**: en Biblioteca, selecciona audio o video y pulsa «Editar metadatos» o elige
  esa acción en el menú contextual. Las fechas se editan por separado como año, mes y día. En audio
  compatible, las etiquetas y la carátula se escriben en el archivo; en video, los metadatos se guardan
  en la biblioteca de PrisDrop. También permite importar/exportar letras `.lrc`, `.txt` y `.srt`.
- **Temas**: el tema integrado «Predeterminado» usa degradados violetas inspirados en PrisDrop.
  El tema oscuro anterior ahora se llama «Oscuro»; «2015» y «W95» también están disponibles.
  Crea temas, ajusta texto secundario, fondos de controles, hover, bordes, selección y otros colores,
  tipografía y animaciones, añade reglas QSS y reemplaza el logotipo,
  icono de aplicación, imagen del reproductor e iconos con archivos SVG o imágenes. El formato ZIP
  incluye los recursos y es la opción recomendada para compartir temas; JSON y QSS no empaquetan imágenes.
  Las imágenes rasterizadas grandes se ajustan a un máximo de 512 × 512 píxeles sin deformar su proporción.
  La selección se conserva al volver a abrir la app. Para el reproductor de audio a pantalla completa,
  personaliza el difuminado de la carátula de fondo, el color y la opacidad de la capa de oscurecimiento.
  También puedes configurar el color de los títulos y la información del reproductor, y activar una
  sombra con color, opacidad, difuminado, tamaño y desplazamientos horizontal/vertical ajustables.
  Los contornos del reproductor y generales también tienen tamaño y desplazamientos independientes.
  Los tamaños y desplazamientos admiten valores decimales. También puedes habilitar
  contornos independientes para los títulos e información del reproductor y para el texto general,
  con color y grosor configurables, y poner el texto general en negrita. Estas opciones se aplican al título y artista
  en el reproductor normal, en la vista de audio completa, al encabezado de recomendaciones y a los
  tiempos transcurrido/total de las barras de reproducción normal y de pantalla completa.
- **Logotipo**: la barra superior usa `PrisDrop-Logotipo.svg` y el icono de la ventana usa
  `PrisDrop-Logo.svg`.
- **Tema 2015**: incluido junto al tema predeterminado y disponible desde **Temas**.
- **Tema W95**: incluye controles de relieve y colores clásicos. Al reproducir audio, el fondo
  del reproductor muestra la carátula difuminada y oscurecida. El difuminado dinámico se renderiza con Qt;
  QSS personaliza los controles y la capa, pero Qt Style Sheets no puede difuminar una imagen en tiempo real.
- **Recomendaciones** debajo del reproductor: videos y música al azar de tu biblioteca (botón «Mezclar»).
- **Páginas**: sección nueva. Pega un enlace web arriba → «Agregar a páginas» → aparece un cuadro; al
  pulsarlo se abre la página dentro de la app. «← Páginas» vuelve. Clic derecho en un cuadro: renombrar/quitar.
- **Capa «Cargando, espera por favor…»**: bloquea la app solo si una acción tarda más de 1 segundo.
- **Error «Sign in to confirm you're not a bot»**: en **Ajustes → Navegador con tu sesión de YouTube**
  elige el navegador donde tienes YouTube con tu cuenta (Firefox recomendado).

## Uso

1. Pega el enlace arriba y pulsa **Analizar** (o **Pegar**, que pega y analiza).
2. Elige **Video** (resolución + MP4/MKV) o **Audio** (Original, MP3, M4A, OPUS, FLAC, WAV, OGG).
3. Pulsa **Descargar**. Las playlists permiten marcar qué elementos bajar.
4. **Biblioteca** → doble clic para reproducir en el **Reproductor**.
5. Para editar audio o video, selecciónalo en **Biblioteca** y abre **Editar metadatos**.
6. Abre **Temas** en la barra lateral para personalizar o importar el diseño. Guarda los cambios del
   tema integrado que quieras conservar; exporta como ZIP para incluir sus imágenes e iconos.

Por defecto, PrisDrop guarda videos en `~/PrisDrop/Videos` y audio en `~/PrisDrop/Musica`.
Si la configuración anterior apuntaba a las carpetas predeterminadas de `~/Descargatube`,
se actualizará a las nuevas rutas; la biblioteca seguirá incluyendo medios que aún permanezcan
en las carpetas antiguas.

## Botón «Actualizar yt-dlp»

Arriba a la derecha. Si hay versión nueva se pone rojo; si ya estás al día dice «✓ yt-dlp actualizado»
y queda deshabilitado.

## Crear el .exe

Ejecuta `build_exe.bat` (PyInstaller, modo sin consola). El ejecutable queda en
`dist\PrisDrop\PrisDrop.exe`; el script solo indica que terminó correctamente si encuentra ese archivo.

Si planeas vender el ejecutable o cambiar su modalidad de distribución, revisa
[LEGAL_CHECKLIST.md](./LEGAL_CHECKLIST.md).
