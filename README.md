# Presupuestos · Top Redes Valencia

App de Streamlit para generar el PDF de presupuesto de TOP REDES VALENCIA
(SOS Madera, S.L.): se rellenan los datos y se descarga el PDF, con el mismo
diseño que el generador HTML.

## Qué hace

- Formulario de cliente, concepto, detalle e importe.
- Importe único **o** desglose por partidas, con descuento fijo, en % o
  indicando el **total final deseado** (el descuento se calcula solo).
- Nota de IVA: «+ IVA 10 % · Total …», «IVA incluido» o ninguna.
  Opción de letra grande para clientes con dificultad visual.
- Fecha, garantía (12 meses / 3 años), cláusula de anclajes, métodos de pago
  y cuño.
- Número y nombre de fichero automáticos: `presupuesto-AAAAMMDD_telefono_INICIALES.pdf`
  (editable, con sufijo opcional `-v2`, `_A`, `_B`…).
- Vista previa y descarga inmediata.
- Historial de la sesión: se puede **volver a cargar un presupuesto en el
  formulario** para modificarlo, y descargar todo en un ZIP con un
  `INDICE.csv`.

## Publicarla en Streamlit Cloud

1. Crea un repositorio **privado** en GitHub y sube el contenido de esta carpeta
   (`app.py`, `generador_pdf.py`, `requirements.txt`, `assets/`, `.streamlit/`).
2. Entra en <https://share.streamlit.io>, pulsa **Create app** y elige el
   repositorio, la rama `main` y el fichero principal `app.py`.
3. Pulsa **Deploy**. La primera vez tarda un par de minutos en instalar
   dependencias.

### Protegerla (importante: contiene datos personales)

La app no guarda nada en disco, pero cualquiera con el enlace podría generar
presupuestos. Dos formas de cerrarla, se pueden combinar:

- **Contraseña propia.** En la app: *Settings → Secrets* y pega
  ```toml
  APP_PASSWORD = "elige-una-contraseña"
  ```
  La app pedirá la contraseña al abrirse. Si no defines este secreto, el acceso
  es libre.
- **Acceso por correo.** En *Settings → Sharing* restringe la visualización a
  tu correo y al de quien deba usarla.

## Limitaciones a tener en cuenta

- **Streamlit Cloud no conserva ficheros.** El historial vive solo mientras la
  pestaña siga abierta; descarga el ZIP antes de cerrar. Si hace falta un
  histórico permanente, habría que conectar una hoja de Google o una base de
  datos.
- Si la app pasa un tiempo sin visitas, Streamlit la «duerme»; al abrirla hay que
  pulsar un botón para despertarla.
- El texto se mide con la fuente Helvetica estándar. Un concepto o detalle muy
  largo reduce la letra automáticamente; la app avisa cuando pasa.
- Los caracteres que la fuente estándar no admite (emojis, algunos alfabetos)
  se sustituyen por su letra base o por «?».

## Probarla en tu ordenador

```bash
pip install -r requirements.txt
streamlit run app.py
```

`python test_app.py` ejecuta unas pruebas automáticas del formulario.

## Estructura

```
app.py              interfaz de Streamlit
generador_pdf.py    diseño del PDF (reportlab, medidas en mm)
assets/             logo e ilustración
.streamlit/         tema de colores
```
