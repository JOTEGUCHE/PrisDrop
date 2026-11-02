# Lista de revisión legal y de licencias para PrisDrop

Este documento es una guía técnica inicial, no asesoría legal ni un contrato. Las licencias,
los binarios y las obligaciones pueden cambiar entre versiones; revisa cada lanzamiento con
un profesional de la jurisdicción donde se venderá.

## Bloqueadores y decisiones previas a la venta

1. **Mutagen es el principal riesgo para distribuir PrisDrop como software propietario.**
   `requirements.txt` incluye `mutagen>=1.47`; PrisDrop importa Mutagen para leer y editar
   metadatos y carátulas. El proyecto declara GPL-2.0-or-later. Antes de vender un ejecutable
   cerrado, reemplázalo por una solución con licencia compatible, obtén una licencia alternativa
   válida si existe para tu caso, o solicita asesoría sobre las obligaciones que asumirías al
   distribuir el conjunto. No des por hecho que empaquetarlo con PyInstaller evita esas obligaciones.
2. **Elige una vía de licencia para Qt for Python.** PySide6/Qt ofrece opciones LGPL/GPL y
   comercial. Si eliges LGPL, revisa las condiciones aplicables a las bibliotecas Qt, plugins,
   avisos y posibilidad de reemplazar bibliotecas en el producto empaquetado. Una licencia
   comercial de Qt puede ser la opción adecuada para ciertos productos cerrados, pero confirma
   su alcance y costo directamente con Qt.
3. **Audita FFmpeg.** `prisdrop/tools.py` descarga el archivo `ffmpeg-master-latest-win64-gpl.zip`
   en Windows y el archivo `ffmpeg-master-latest-linux64-gpl.tar.xz` en Linux. El sufijo `gpl`
   indica que no se debe tratar como una compilación LGPL genérica. Conserva la licencia, avisos,
   fuentes y datos de compilación que correspondan a los binarios efectivamente descargados;
   evalúa también los códecs y sus posibles patentes en los territorios de venta. Otra
   compilación puede tener obligaciones distintas.

## Inventario actual que debe confirmarse por lanzamiento

| Componente | Uso en PrisDrop | Licencia indicada por el proyecto |
|---|---|---|
| Mutagen | Metadatos de audio y carátulas | GPL-2.0-or-later |
| PySide6 / Qt | Interfaz, multimedia y widgets | LGPL/GPL o comercial, según la opción aplicable |
| FFmpeg | Ejecutables descargados por PrisDrop | La compilación seleccionada se etiqueta `gpl`; verifica sus componentes |
| yt-dlp | Descarga como ejecutable oficial independiente | Unlicense |
| Deno | Runtime descargado para yt-dlp | MIT |
| PyInstaller | Empaquetado del ejecutable | GPL con excepción para aplicaciones generadas; algunos archivos Apache-2.0 |
| PyWinRT | Acceso a los controles multimedia de Windows | MIT |

Este inventario no reemplaza el análisis del contenido real de cada instalador. Incluye también
las dependencias transitivas, plugins Qt, archivos de idioma, iconos, fuentes, temas, códecs y
cualquier binario que PrisDrop descargue o actualice. El uso de PyInstaller no elimina las
obligaciones de las dependencias incluidas.

## Preparación de cada versión distribuida

- Genera y conserva una lista/SBOM de paquetes, versiones, licencias, archivos y hashes de cada
  instalador y de las herramientas descargadas posteriormente.
- Guarda una copia de las licencias y avisos exactos de las versiones redistribuidas y agrega
  los avisos exigidos dentro de la aplicación o junto a la descarga.
- Verifica que la versión publicada corresponda a las fuentes y compilaciones de las que puedes
  ofrecer el código fuente cuando una licencia lo requiera.
- Revisa los términos de Qt, FFmpeg y cada códec en las jurisdicciones de venta. No afirmes que
  todo el producto es propietario hasta resolver las obligaciones de Mutagen y de cada componente.
- Mantén un registro del titular de los derechos de PrisDrop, del material gráfico propio y de
  las licencias o permisos de recursos de terceros.

## Términos de venta, privacidad y uso

Antes de vender, redacta y revisa con asesoría local, como mínimo:

- Identidad del vendedor, países/territorios cubiertos, contacto y ley aplicable.
- Qué licencia recibe la persona usuaria, dispositivos permitidos, actualizaciones, soporte y
  causas de suspensión o terminación.
- Precio, impuestos, renovación si la hubiera, cancelación, devoluciones y derechos irrenunciables
  de consumidores de cada territorio.
- Garantías, disponibilidad, límites de responsabilidad y restricciones que permita la ley local.
- Política de privacidad: datos realmente tratados, almacenamiento local, telemetría (si existe),
  pagos, soporte, descargas y servicios externos; finalidad, retención, transferencias y contacto.
- Reglas de uso responsable: contar con los derechos y permisos para descargar, convertir o
  redistribuir contenido, y respetar los términos de las plataformas de origen y los derechos de
  terceros. No prometas que una descarga concreta está autorizada por el titular.

La aplicación contacta servicios externos para descargar/actualizar yt-dlp, FFmpeg y Deno, y
usa yt-dlp para procesar enlaces proporcionados por la persona usuaria. Confirma los datos que
se envían realmente en cada flujo antes de describirlos en la política de privacidad. No se han
redactado aquí un EULA, términos de venta ni una política de privacidad definitiva.

## Fuentes de referencia

- [Mutagen en PyPI](https://pypi.org/project/mutagen/)
- [Licencias de Qt](https://www.qt.io/development/qt-framework/qt-licensing)
- [Consideraciones de licencia de Qt for Python](https://doc.qt.io/qtforpython-6/licenses.html)
- [Aspectos legales y licencias de FFmpeg](https://ffmpeg.org/legal.html)
- [Licencia de yt-dlp](https://github.com/yt-dlp/yt-dlp/blob/master/LICENSE)
- [Licencia de Deno](https://github.com/denoland/deno/blob/main/LICENSE)
- [Licencia de PyInstaller](https://pyinstaller.org/en/stable/license.html)
- [Licencia de PyWinRT](https://github.com/pywinrt/pywinrt/blob/main/LICENSE)
