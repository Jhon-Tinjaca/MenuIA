import json
import os
import tempfile
import time
import gradio as gr
import pandas as pd
from google import genai
from google.genai import types

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
client = genai.Client(api_key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None

MODELO_PRINCIPAL = "gemini-3.8-flash"
MODELO_RESPALDO = "gemini-3.5-flash-lite"


def generar_contenido_con_reintento(imagen, prompt):
    modelos = [MODELO_PRINCIPAL, MODELO_RESPALDO]
    ultimo_error = None

    for modelo in modelos:
        for intento in range(3):
            try:
                return client.models.generate_content(
                    model=modelo,
                    contents=[imagen, prompt],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                    ),
                )
            except Exception as e:
                ultimo_error = e
                es_503 = "503" in str(e) or "UNAVAILABLE" in str(e).upper()
                if es_503 and intento < 2:
                    time.sleep(2 ** intento)
                    continue
                if es_503:
                    break
                raise

    raise ultimo_error


def procesar_menu_gradio(imagen):
    if not client:
        return "❌ Error: API Key de Gemini no configurada.", None
    if imagen is None:
        return "⚠️ Por favor, sube una imagen.", None

    try:
        prompt = (
            "Eres un asistente experto en extracción de datos. Analiza esta imagen de un menú de restaurante. "
            "Extrae el nombre del restaurante (si es visible, si no pon 'Desconocido'), "
            "todos los productos, sus ingredientes (si los hay) y sus precios. "
            "Devuelve un arreglo en formato JSON donde cada elemento represente un producto y tenga "
            "exactamente estas cuatro claves: 'Producto', 'Ingredientes', 'Precio', 'Restaurante'."
        )

        response = generar_contenido_con_reintento(imagen, prompt)
        datos = json.loads(response.text)

        if isinstance(datos, dict):
            productos = datos.get("productos") or datos.get("items") or [datos]
        elif isinstance(datos, list):
            productos = datos
        else:
            productos = []

        if not productos:
            return "⚠️ No se pudo extraer ningún producto de la imagen.", None

        df = pd.DataFrame(productos)
        if "Restaurante" in df.columns:
            cols = [c for c in df.columns if c != "Restaurante"] + ["Restaurante"]
            df = df[cols]

        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            ruta_excel = tmp.name

        df.to_excel(ruta_excel, index=False)
        return f"✅ ¡Procesado con éxito! Se extrajeron {len(productos)} productos.", ruta_excel

    except Exception as e:
        return f"❌ Error: {str(e)}", None


with gr.Blocks() as demo:
    gr.Markdown("<h1 style='text-align: center; color: #1a73e8;'>🍽️ Extractor de Menús IA</h1>")
    gr.Markdown("<p style='text-align: center;'>Sube la foto del menú y deja que la IA extraiga los productos.</p>")

    with gr.Row():
        with gr.Column():
            imagen_entrada = gr.Image(type="pil", label="Sube tu Menú (Imagen)", sources=["upload"])
            boton_procesar = gr.Button("⚡ Procesar Menú", variant="primary")
        with gr.Column():
            texto_salida = gr.Textbox(label="Estado del Proceso", interactive=False)
            archivo_salida = gr.File(label="Descargar Excel")

    boton_procesar.click(
        fn=procesar_menu_gradio,
        inputs=[imagen_entrada],
        outputs=[texto_salida, archivo_salida],
    )

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", 7860)),
    )
