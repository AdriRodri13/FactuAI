import json
import requests

DEEPSEEK_API_KEY = "sk-235698e301a34fe19d18f2069a08fef8" 
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

class ProcesadorOCR:

    @staticmethod
    def procesar_texto(texto_ocr):
        if not texto_ocr or not DEEPSEEK_API_KEY:
            return {"error": "Falta texto OCR o clave de API"}

        prompt = f"""
                    Analiza el siguiente texto OCR extraído de una factura. Devuelve un JSON con solo estos campos:
                    {{
                    "empresa": "",
                    "numero_factura": "",
                    "fecha": ""
                    }}

                    Texto OCR:
                    {texto_ocr}
                """

        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "Eres un experto en facturas españolas."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }

        try:
            respuesta = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload)
            if respuesta.status_code == 200:
                contenido = respuesta.json()['choices'][0]['message']['content']
                # Extraer solo el JSON aunque venga formateado como bloque de código
                if "```json" in contenido:
                    contenido = contenido.split("```json")[1].split("```")[0].strip()
                elif "```" in contenido:
                    contenido = contenido.split("```")[1].split("```")[0].strip()
                return json.loads(contenido)
            else:
                return {"error": f"Error HTTP {respuesta.status_code}: {respuesta.text}"}
        except Exception as e:
            return {"error": f"Excepción al llamar a DeepSeek: {str(e)}"}
