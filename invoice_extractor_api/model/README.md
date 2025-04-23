# Modelo de Extracción de Facturas

Esta carpeta debe contener los archivos del modelo fine-tuneado de Hugging Face.

## Estructura del Modelo

Coloca aquí los archivos necesarios del modelo, típicamente:
- `config.json`
- `pytorch_model.bin`
- `tokenizer_config.json`
- `tokenizer.json`
- `vocab.json`
- `special_tokens_map.json`

## Actualización del Modelo

Para actualizar el modelo:

1. Detén el servidor de Django si está en ejecución
2. Reemplaza los archivos en esta carpeta con los nuevos archivos del modelo
3. Asegúrate de mantener los mismos nombres de archivos
4. Reinicia el servidor de Django

Alternativamente, puedes dejar el servidor en ejecución y usar el endpoint `/api/reload-model/` para cargar el nuevo modelo después de reemplazar los archivos.

## Recomendaciones

- Mantén respaldos de versiones anteriores del modelo
- Documenta los cambios realizados en cada versión
- Realiza pruebas de integración antes de actualizar el modelo en producción