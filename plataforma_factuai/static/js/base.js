        document.addEventListener('DOMContentLoaded', function() {
            // Inicialización de tooltips
            var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'))
            var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
              return new bootstrap.Tooltip(tooltipTriggerEl)
            });
            
            // Manejo del toggle de sidebar en móvil
            const sidebarToggle = document.getElementById('sidebarToggle');
            if (sidebarToggle) {
                sidebarToggle.addEventListener('click', function() {
                    const sidebar = document.querySelector('.sidebar');
                    sidebar.classList.toggle('show');
                    
                    // Agregar overlay para cerrar sidebar al hacer clic fuera
                    if (sidebar.classList.contains('show')) {
                        const overlay = document.createElement('div');
                        overlay.id = 'sidebarOverlay';
                        overlay.style.position = 'fixed';
                        overlay.style.top = '0';
                        overlay.style.left = '0';
                        overlay.style.width = '100%';
                        overlay.style.height = '100%';
                        overlay.style.backgroundColor = 'rgba(0, 0, 0, 0.5)';
                        overlay.style.zIndex = '999';
                        overlay.style.opacity = '0';
                        overlay.style.transition = 'opacity 0.3s ease';
                        document.body.appendChild(overlay);
                        setTimeout(() => {
                            overlay.style.opacity = '1';
                        }, 10);
                        
                        overlay.addEventListener('click', function() {
                            sidebar.classList.remove('show');
                            overlay.style.opacity = '0';
                            setTimeout(() => {
                                overlay.remove();
                            }, 300);
                        });
                    } else {
                        const overlay = document.getElementById('sidebarOverlay');
                        if (overlay) {
                            overlay.style.opacity = '0';
                            setTimeout(() => {
                                overlay.remove();
                            }, 300);
                        }
                    }
                });
            }
            
            // Animación de entrada para contenido principal
            const mainContent = document.querySelector('.main-content');
            if (mainContent) {
                mainContent.classList.add('fade-in');
            }
        });
        
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
            const toast = new bootstrap.Toast(toastElement, { 
                delay: 5000,
                animation: true
            });
            toast.show();
            
            // Animación de entrada
            toastElement.style.transform = 'translateY(20px)';
            toastElement.style.opacity = '0';
            toastElement.style.transition = 'all 0.3s ease';
            
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