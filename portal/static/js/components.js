/* ============================================
   components.js — Componentes reutilizáveis
   ============================================ */

const Components = {
    loading() {
        return `<div class="loading"><div class="loading-spinner"></div></div>`;
    },

    skeleton(n = 3) {
        return Array(n).fill('<div class="skeleton"></div>').join('');
    },

    alert(msg, tipo = 'info') {
        return `<div class="alert alert-${tipo}">${msg}</div>`;
    },

    card(label, title, subtitle = '', extras = '', cardClass = '') {
        return `
            <div class="card ${cardClass}">
                ${label ? `<div class="card-label">${label}</div>` : ''}
                <div class="card-title">${title}</div>
                ${subtitle ? `<div class="card-subtitle">${subtitle}</div>` : ''}
                ${extras}
            </div>`;
    },

    emptyState(icon, msg) {
        return `<div class="empty-state"><div class="empty-icon">${icon}</div><p>${msg}</p></div>`;
    },

    modal(id, title, content) {
        return `
            <div class="modal-overlay" id="${id}-overlay" onclick="Components.closeModal('${id}')">
                <div class="modal" onclick="event.stopPropagation()">
                    <div class="modal-handle"></div>
                    <div class="modal-title">${title}</div>
                    ${content}
                </div>
            </div>`;
    },

    openModal(id) {
        document.getElementById(`${id}-overlay`)?.classList.add('open');
    },

    closeModal(id) {
        document.getElementById(`${id}-overlay`)?.classList.remove('open');
    },
};
