document.addEventListener('DOMContentLoaded', function() {
    const dropZone = document.getElementById('dropZone');
    const fileInput = document.getElementById('fileInput');
    const browseBtn = document.getElementById('browseBtn');
    const fileList = document.getElementById('fileList');
    const fileListItems = document.getElementById('fileListItems');
    const submitBtn = document.getElementById('submitBtn');
    const uploadForm = document.getElementById('uploadForm');
    const progressBar = document.getElementById('uploadProgress');
    const progressWrapper = document.querySelector('.progress-wrapper');
    
    // Crear una colección de archivos que se pueda modificar
    let selectedFiles = new DataTransfer();
    
    // Aplicar animaciones de entrada
    const elements = document.querySelectorAll('.fade-in');
    elements.forEach((el, index) => {
        el.style.opacity = '0';
        setTimeout(() => {
            el.style.opacity = '1';
        }, 100 * index);
    });
    
    // Manejar click en botón de explorar
    browseBtn.addEventListener('click', function() {
        fileInput.click();
    });
    
    // Manejar cambio en input de archivo
    fileInput.addEventListener('change', function() {
        handleFiles(this.files);
    });
    
    // Prevenir comportamiento por defecto de drag and drop
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });
    
    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    // Añadir/quitar clase para efectos visuales
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, highlight, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, unhighlight, false);
    });
    
    function highlight() {
        dropZone.classList.add('dragover');
    }
    
    function unhighlight() {
        dropZone.classList.remove('dragover');
    }
    
    // Manejar drop
    dropZone.addEventListener('drop', function(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    });
    
    // Formatear tamaño de archivo
    function formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    // Actualizar contador de archivos
    function updateFileCounter() {
        const fileCount = selectedFiles.files.length;
        if (fileCount > 0) {
            const fileHeader = fileList.querySelector('.card-header h5');
            fileHeader.innerHTML = `<i class="fas fa-file-alt me-2"></i>Archivos Seleccionados <span class="badge bg-primary ms-2">${fileCount}</span>`;
        }
    }
    
    // Función para manejar archivos
    function handleFiles(files) {
        if (files.length === 0) return;
        
        // Limpiar la lista visual
        fileListItems.innerHTML = '';
        
        // Actualizar la colección de archivos
        selectedFiles = new DataTransfer();
        Array.from(files).forEach(file => {
            // Verificar extensión
            const ext = file.name.split('.').pop().toLowerCase();
            const allowedExts = ['pdf', 'jpg', 'jpeg', 'png', 'zip', 'rar'];
            
            if (!allowedExts.includes(ext)) {
                showToast(`El archivo ${file.name} no es un formato permitido.`, 'danger');
                return;
            }
            
            // Verificar tamaño
            const maxSize = 50 * 1024 * 1024; // 50MB
            if (file.size > maxSize) {
                showToast(`El archivo ${file.name} excede el tamaño máximo permitido (50MB).`, 'danger');
                return;
            }
            
            // Añadir a la colección
            selectedFiles.items.add(file);
        });
        
        // Actualizar el input de archivos
        fileInput.files = selectedFiles.files;
        
        // Si no hay archivos válidos, salir
        if (selectedFiles.files.length === 0) return;
        
        // Mostrar la lista y el botón de subir
        fileList.style.display = 'block';
        submitBtn.style.display = 'block';
        
        // Mostrar cada archivo en la lista con animación
        Array.from(selectedFiles.files).forEach((file, index) => {
            const ext = file.name.split('.').pop().toLowerCase();
            const fileItem = document.createElement('li');
            fileItem.className = 'list-group-item file-item';
            fileItem.style.opacity = '0';
            fileItem.style.transform = 'translateY(10px)';
            fileItem.style.transition = 'all 0.3s ease';
            
            // Seleccionar icono según tipo
            let iconClass = 'fa-file';
            if (ext === 'pdf') iconClass = 'fa-file-pdf';
            else if (['jpg', 'jpeg', 'png'].includes(ext)) iconClass = 'fa-file-image';
            else if (ext === 'zip' || ext === 'rar') iconClass = 'fa-file-archive';
            
            fileItem.innerHTML = `
                <i class="fas ${iconClass} file-icon"></i>
                <span class="file-name">${file.name}</span>
                <span class="file-size text-muted">${formatFileSize(file.size)}</span>
                <div class="file-remove" onclick="removeFile(this)">
                    <i class="fas fa-times"></i>
                </div>
            `;
            
            fileListItems.appendChild(fileItem);
            
            // Animación de entrada escalonada
            setTimeout(() => {
                fileItem.style.opacity = '1';
                fileItem.style.transform = 'translateY(0)';
            }, 50 * index);
        });
        
        // Actualizar contador
        updateFileCounter();
    }
    
    // Manejar envío del formulario
    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault();
        
        if (fileInput.files.length === 0) {
            showToast('Por favor, selecciona al menos un archivo para subir.', 'warning');
            return;
        }
        
        // Mostrar barra de progreso
        progressWrapper.style.display = 'block';
        
        // Desactivar botón de subida
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Subiendo...';
        
        // Crear FormData y añadir archivos
        const formData = new FormData(uploadForm);
        
        // Crear y configurar petición AJAX
        const xhr = new XMLHttpRequest();
        xhr.open('POST', uploadForm.action || window.location.href, true);
        
        // Manejar progreso de subida
        xhr.upload.addEventListener('progress', function(e) {
            if (e.lengthComputable) {
                const percentComplete = Math.round((e.loaded / e.total) * 100);
                progressBar.style.width = percentComplete + '%';
                progressBar.textContent = percentComplete + '%';
            }
        });
        
        // Manejar respuesta
        xhr.onload = function() {
            if (xhr.status === 200) {
                // Mostrar notificación de éxito
                showToast('¡Tus archivos se han subido correctamente!', 'success');
                
                // Redirigir a la página que devuelve el servidor después de un breve retraso
                setTimeout(() => {
                    window.location.href = xhr.responseURL;
                }, 1500);
            } else {
                // Mostrar error
                showToast('Error al subir los archivos. Por favor, inténtalo de nuevo.', 'danger');
                submitBtn.disabled = false;
                submitBtn.innerHTML = '<i class="fas fa-upload me-2"></i>Subir Archivos';
            }
        };
        
        // Manejar error
        xhr.onerror = function() {
            showToast('Error de conexión. Por favor, inténtalo de nuevo.', 'danger');
            submitBtn.disabled = false;
            submitBtn.innerHTML = '<i class="fas fa-upload me-2"></i>Subir Archivos';
        };
        
        // Enviar petición
        xhr.send(formData);
    });
});

// Función para eliminar archivo de la lista
function removeFile(element) {
    // Encontrar y remover el elemento de la lista
    const item = element.closest('.file-item');
    const fileName = item.querySelector('.file-name').textContent;
    
    // Animar salida
    item.style.opacity = '0';
    item.style.transform = 'translateX(10px)';
    
    setTimeout(() => {
        item.remove();
        
        // Eliminar el archivo del DataTransfer
        const fileInput = document.getElementById('fileInput');
        const fileList = document.getElementById('fileList');
        const submitBtn = document.getElementById('submitBtn');
        const fileListItems = document.getElementById('fileListItems');
        
        // Crear un nuevo DataTransfer
        const newFileList = new DataTransfer();
        for (let i = 0; i < fileInput.files.length; i++) {
            if (fileInput.files[i].name !== fileName) {
                newFileList.items.add(fileInput.files[i]);
            }
        }
        
        // Actualizar el input de archivos
        fileInput.files = newFileList.files;
        
        // Verificar si quedan archivos
        if (fileListItems.children.length === 0) {
            fileList.style.display = 'none';
            submitBtn.style.display = 'none';
        } else {
            // Actualizar contador
            const fileCount = fileInput.files.length;
            if (fileCount > 0) {
                const fileHeader = fileList.querySelector('.card-header h5');
                fileHeader.innerHTML = `<i class="fas fa-file-alt me-2"></i>Archivos Seleccionados <span class="badge bg-primary ms-2">${fileCount}</span>`;
            }
        }
    }, 300);
}

// Función para mostrar notificaciones toast
function showToast(message, type = 'info') {
    const toastContainer = document.querySelector('.toast-container');
    const toastId = `toast-${Date.now()}`;
    
    // Seleccionar icono según tipo de mensaje
    let icon = 'info-circle';
    if (type === 'success') icon = 'check-circle';
    if (type === 'warning') icon = 'exclamation-circle';
    if (type === 'danger' || type === 'error') icon = 'exclamation-triangle';
    
    const toastHTML = `
        <div id="${toastId}" class="toast align-items-center text-white bg-${type}" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    <i class="fas fa-${icon} me-2"></i>
                    ${message}
                </div>
                <button type="button" class="btn-close me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    
    toastContainer.insertAdjacentHTML('beforeend', toastHTML);
    const toastElement = document.getElementById(toastId);
    
    // Aplicar animación de entrada
    toastElement.style.transform = 'translateY(20px)';
    toastElement.style.opacity = '0';
    toastElement.style.transition = 'all 0.3s ease';
    
    const toast = new bootstrap.Toast(toastElement, { delay: 5000 });
    toast.show();
    
    setTimeout(() => {
        toastElement.style.transform = 'translateY(0)';
        toastElement.style.opacity = '1';
    }, 50);
    
    // Auto-eliminar después de ocultarse
    toastElement.addEventListener('hidden.bs.toast', function () {
        toastElement.style.transform = 'translateY(-20px)';
        toastElement.style.opacity = '0';
        setTimeout(() => {
            toastElement.remove();
        }, 300);
    });
}