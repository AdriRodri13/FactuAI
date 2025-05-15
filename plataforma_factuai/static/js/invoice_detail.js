document.addEventListener('DOMContentLoaded', function() {
    // Funcionalidad de zoom para la imagen de factura
    const imageContainer = document.getElementById('imageContainer');
    const invoiceImage = document.getElementById('invoiceImage');
    const zoomIn = document.getElementById('zoomIn');
    const zoomOut = document.getElementById('zoomOut');
    const resetZoom = document.getElementById('resetZoom');
    
    let scale = 1;
    const maxScale = 3;
    const minScale = 0.5;
    const scaleStep = 0.2;
    
    // Función para aplicar zoom
    function applyZoom() {
        invoiceImage.style.transform = `scale(${scale})`;
        invoiceImage.style.transformOrigin = 'top left';
    }
    
    // Zoom in
    if (zoomIn) {
        zoomIn.addEventListener('click', function() {
            if (scale < maxScale) {
                scale += scaleStep;
                applyZoom();
            }
        });
    }
    
    // Zoom out
    if (zoomOut) {
        zoomOut.addEventListener('click', function() {
            if (scale > minScale) {
                scale -= scaleStep;
                applyZoom();
            }
        });
    }
    
    // Reset zoom
    if (resetZoom) {
        resetZoom.addEventListener('click', function() {
            scale = 1;
            applyZoom();
        });
    }
    
    // Formatear JSON para mejor visualización
    const jsonViewer = document.getElementById('jsonViewer');
    if (jsonViewer) {
        try {
            const jsonData = JSON.parse(jsonViewer.querySelector('pre').textContent);
            jsonViewer.querySelector('pre').textContent = JSON.stringify(jsonData, null, 2);
        } catch (e) {
            // Si no es un JSON válido, dejarlo como está
            console.log('No se pudo parsear el JSON:', e);
        }
    }
});