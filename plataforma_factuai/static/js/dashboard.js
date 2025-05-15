document.addEventListener('DOMContentLoaded', function() {
    // Inicializar tooltips de Bootstrap
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Verificar estado de documentos que están en procesamiento
    const processingDocs = document.querySelectorAll('.doc-item:has(.processing-animation)');
    
    if (processingDocs.length > 0) {
        // Configurar intervalo para actualizar estado
        setInterval(checkProcessingStatus, 5000);
    }
    
    function checkProcessingStatus() {
        processingDocs.forEach(docItem => {
            const docId = docItem.dataset.id;
            
            // Realizar petición AJAX para verificar estado
            fetch(PROCESS_STATUS_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ document_id: docId })
            })
            .then(response => response.json())
            .then(data => {
                // Actualizar estado en la interfaz
                const statusCell = docItem.querySelector('td:nth-child(3)');
                
                if (data.processed) {
                    statusCell.innerHTML = '<span class="badge bg-success doc-status-badge">Procesado</span>';
                } else if (data.error) {
                    statusCell.innerHTML = `<span class="badge bg-danger doc-status-badge" data-bs-toggle="tooltip" title="${data.error}">Error</span>`;
                    
                    // Inicializar tooltip para el nuevo elemento
                    new bootstrap.Tooltip(statusCell.querySelector('[data-bs-toggle="tooltip"]'));
                    
                    // Añadir botón de reintentar
                    const actionsCell = docItem.querySelector('td:nth-child(4) .btn-group');
                    if (!actionsCell.querySelector('.retry-doc')) {
                        actionsCell.innerHTML += `
                            <button class="btn btn-sm btn-outline-primary retry-doc" data-id="${docId}">
                                <i class="fas fa-redo"></i>
                            </button>
                        `;
                    }
                } else {
                    // Actualizar progreso si está disponible
                    statusCell.innerHTML = `
                        <span class="badge bg-info doc-status-badge">
                            <div class="processing-animation me-1"></div>
                            Procesando ${data.progress}%
                        </span>
                    `;
                }
            })
            .catch(error => console.error('Error:', error));
        });
    }
    
    // Manejar click en botón de reintentar
    document.addEventListener('click', function(e) {
        if (e.target.closest('.retry-doc')) {
            const button = e.target.closest('.retry-doc');
            const docId = button.dataset.id;
            
            // Cambiar apariencia del botón
            button.disabled = true;
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            
            // Realizar petición AJAX para reintentar procesamiento
            fetch(RETRY_PROCESSING_URL, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCsrfToken()
                },
                body: JSON.stringify({ document_id: docId })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Actualizar estado en la interfaz
                    const docItem = button.closest('.doc-item');
                    const statusCell = docItem.querySelector('td:nth-child(3)');
                    statusCell.innerHTML = `
                        <span class="badge bg-info doc-status-badge">
                            <div class="processing-animation me-1"></div>
                            Procesando
                        </span>
                    `;
                    
                    // Eliminar botón de reintentar
                    button.remove();
                    
                    showToast('Procesamiento reiniciado correctamente', 'success');
                } else {
                    button.disabled = false;
                    button.innerHTML = '<i class="fas fa-redo"></i>';
                    showToast('Error al reintentar procesamiento', 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                button.disabled = false;
                button.innerHTML = '<i class="fas fa-redo"></i>';
                showToast('Error al reintentar procesamiento', 'danger');
            });
        }
    });
    
    // Función para obtener el token CSRF
    function getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }
    
    // Función para mostrar notificaciones toast
    function showToast(message, type) {
        const toastContainer = document.querySelector('.toast-container');
        
        const toastEl = document.createElement('div');
        toastEl.className = `toast align-items-center border-0 text-white bg-${type}`;
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');
        toastEl.setAttribute('aria-atomic', 'true');
        
        const icon = type === 'success' ? 'check-circle' : 
                     type === 'danger' ? 'exclamation-circle' : 'info-circle';
        
        toastEl.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-${icon} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        `;
        
        toastContainer.appendChild(toastEl);
        
        const toast = new bootstrap.Toast(toastEl, {
            autohide: true,
            delay: 3000
        });
        
        toast.show();
        
        // Eliminar toast del DOM después de ocultarse
        toastEl.addEventListener('hidden.bs.toast', function() {
            toastEl.remove();
        });
    }
});