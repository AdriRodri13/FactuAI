document.addEventListener('DOMContentLoaded', function() {
    // Referencias a elementos
    const editCompanyBtn = document.getElementById('editCompanyBtn');
    const cancelEditBtn = document.getElementById('cancelEditBtn');
    const saveCompanyBtn = document.getElementById('saveCompanyBtn');
    const deleteCompanyBtn = document.getElementById('deleteCompanyBtn');
    const confirmDeleteBtn = document.getElementById('confirmDeleteBtn');
    const viewMode = document.getElementById('viewMode');
    const editMode = document.getElementById('editMode');
    const editCompanyForm = document.getElementById('editCompanyForm');
    const deleteConfirmModal = document.getElementById('deleteConfirmModal');
    
    // Manejar la edición de la empresa
    if (editCompanyBtn) {
        editCompanyBtn.addEventListener('click', function() {
            viewMode.style.display = 'none';
            editMode.style.display = 'block';
            
            // Enfocar el primer campo
            document.getElementById('editNombre').focus();
        });
    }
    
    // Manejar la cancelación de la edición
    if (cancelEditBtn) {
        cancelEditBtn.addEventListener('click', function() {
            viewMode.style.display = 'block';
            editMode.style.display = 'none';
            
            // Resetear el formulario para descartar cambios
            editCompanyForm.reset();
        });
    }
    
    // Manejar el guardado de cambios
    if (editCompanyForm) {
        editCompanyForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            // Validar formulario
            if (!this.checkValidity()) {
                this.reportValidity();
                return;
            }
            
            // Obtener datos del formulario
            const empresaId = document.getElementById('empresaId').value;
            const nombre = document.getElementById('editNombre').value;
            const nif = document.getElementById('editNif').value;
            const direccion = document.getElementById('editDireccion').value;
            const telefono = document.getElementById('editTelefono').value;
            const email = document.getElementById('editEmail').value;
            
            // Desactivar botón durante procesamiento
            saveCompanyBtn.disabled = true;
            saveCompanyBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Guardando...';
            
            // Enviar datos al servidor
            fetch(`/empresa/actualizar/${empresaId}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: JSON.stringify({
                    nombre: nombre,
                    nif: nif,
                    direccion: direccion,
                    telefono: telefono,
                    email: email
                })
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Error en la respuesta del servidor: ' + response.status);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Mostrar mensaje de éxito
                    showToast('Empresa actualizada correctamente', 'success');
                    
                    // Cambiar a modo visualización
                    viewMode.style.display = 'block';
                    editMode.style.display = 'none';
                    
                    // Actualizar los datos mostrados sin recargar la página
                    updateCompanyInfo(data.empresa);
                } else {
                    // Mostrar error
                    showToast(data.error || 'Error al actualizar la empresa', 'error');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showToast('Error al actualizar la empresa', 'error');
            })
            .finally(() => {
                // Restaurar botón
                saveCompanyBtn.disabled = false;
                saveCompanyBtn.innerHTML = '<i class="fas fa-save me-2"></i>Guardar Cambios';
            });
        });
    }
    
    // Manejar la eliminación de la empresa
    if (deleteCompanyBtn) {
        deleteCompanyBtn.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Abrir modal de confirmación
            const modal = new bootstrap.Modal(deleteConfirmModal, {
                backdrop: false,
                keyboard: true
            });
            modal.show();
        });
    }
    
    // Manejar la confirmación de eliminación
    if (confirmDeleteBtn) {
        confirmDeleteBtn.addEventListener('click', function() {
            // Obtener ID de la empresa
            const empresaId = document.getElementById('empresaId').value;
            
            // Desactivar botón durante procesamiento
            this.disabled = true;
            this.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Eliminando...';
            
            // Enviar solicitud de eliminación
            fetch(`/empresa/eliminar/${empresaId}/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCookie('csrftoken')
                }
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('Error en la respuesta del servidor: ' + response.status);
                }
                return response.json();
            })
            .then(data => {
                if (data.success) {
                    // Mostrar mensaje de éxito
                    showToast('Empresa eliminada correctamente', 'success');
                    
                    // Redirigir al listado de empresas después de un breve retraso
                    setTimeout(() => {
                        window.location.href = '/empresas/';
                    }, 1500);
                } else {
                    // Mostrar error
                    showToast(data.error || 'Error al eliminar la empresa', 'error');
                    
                    // Restaurar botón
                    this.disabled = false;
                    this.innerHTML = '<i class="fas fa-trash-alt me-2"></i>Sí, eliminar empresa';
                    
                    // Cerrar modal
                    const modal = bootstrap.Modal.getInstance(deleteConfirmModal);
                    modal.hide();
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showToast('Error al eliminar la empresa', 'error');
                
                // Restaurar botón
                this.disabled = false;
                this.innerHTML = '<i class="fas fa-trash-alt me-2"></i>Sí, eliminar empresa';
                
                // Cerrar modal
                const modal = bootstrap.Modal.getInstance(deleteConfirmModal);
                modal.hide();
            });
        });
    }
    
    // Función para actualizar la información mostrada
    function updateCompanyInfo(empresa) {
        // Actualizar título de la página
        document.title = `${empresa.nombre} - Detalles de Empresa | FactuAI`;
        document.querySelector('.company-title').textContent = empresa.nombre;
        
        // Actualizar todos los campos en modo visualización
        const infoGroups = viewMode.querySelectorAll('.info-group');
        infoGroups.forEach(group => {
            const label = group.querySelector('.info-label').textContent.trim();
            const valueElement = group.querySelector('.info-value');
            
            switch(label) {
                case 'Nombre':
                    valueElement.textContent = empresa.nombre;
                    break;
                case 'NIF':
                    valueElement.textContent = empresa.nif || 'No especificado';
                    break;
                case 'Dirección':
                    valueElement.textContent = empresa.direccion || 'No especificada';
                    break;
                case 'Teléfono':
                    valueElement.textContent = empresa.telefono || 'No especificado';
                    break;
                case 'Email':
                    valueElement.textContent = empresa.email || 'No especificado';
                    break;
                case 'Última Actualización':
                    // Formatear fecha
                    const date = new Date(empresa.fecha_actualizacion);
                    valueElement.textContent = date.toLocaleString('es-ES');
                    break;
            }
        });
        
        // Actualizar badge de NIF si existe
        const nifBadge = document.querySelector('.badge:contains("NIF:")');
        if (nifBadge && empresa.nif) {
            nifBadge.textContent = `NIF: ${empresa.nif}`;
        }
    }
    
    // Función para obtener CSRF token
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    // Función para mostrar notificaciones toast
    function showToast(message, type = 'info') {
        const toastContainer = document.querySelector('.toast-container') || createToastContainer();
        
        const toastEl = document.createElement('div');
        toastEl.className = `toast align-items-center border-0 text-white bg-${type === 'error' ? 'danger' : type}`;
        toastEl.setAttribute('role', 'alert');
        toastEl.setAttribute('aria-live', 'assertive');
        toastEl.setAttribute('aria-atomic', 'true');
        
        toastEl.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-${type === 'success' ? 'check-circle' : type === 'error' ? 'exclamation-circle' : 'info-circle'} me-2"></i>
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
    
    // Función para crear el contenedor de toasts si no existe
    function createToastContainer() {
        const container = document.createElement('div');
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        document.body.appendChild(container);
        return container;
    }
    
    
});