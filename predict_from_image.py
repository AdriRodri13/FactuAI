import torch
from transformers import T5Tokenizer, T5ForConditionalGeneration
from PIL import Image
import pytesseract
import os

# 📍 Paths
MODEL_PATH = "data/trained_extractor_model"
IMAGE_PATH = "imagen2.jpg"

# 🧠 Configuración OCR
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # Ajusta si está en otra ruta
LANG = "spa"  # Cambia a "eng" si no tienes el español

# 🔍 OCR
print("🖼️ Leyendo imagen...")
image = Image.open(IMAGE_PATH).convert("RGB")
ocr_text = pytesseract.image_to_string(image, lang=LANG)

print("\n🔍 Texto OCR:")
print(ocr_text)

# 📝 Input para el modelo
input_text = ocr_text.strip()

print("\n📝 Texto enviado al modelo:")
print("extrae_info: " + input_text)

# ⚙️ Cargar modelo
print("\n⚙️ Cargando modelo...")
device = "cuda" if torch.cuda.is_available() else "cpu"
tokenizer = T5Tokenizer.from_pretrained(MODEL_PATH)
model = T5ForConditionalGeneration.from_pretrained(MODEL_PATH).to(device)

# 🔧 Tokenizar input
inputs = tokenizer(
    "extrae_info: " + input_text,
    return_tensors="pt",
    truncation=True,
    padding="max_length",
    max_length=512
).to(device)

# 🚀 Generar predicción
print("\n🚀 Generando predicción...")
output_ids = model.generate(
    **inputs,
    max_length=128,
    num_beams=4,
    early_stopping=True
)

# 🧾 Decodificar
predicted_text = tokenizer.decode(output_ids[0], skip_special_tokens=True)

print("\n🧠 Predicción:")
print(predicted_text)
