/**
 * Tyre Invoice Consolidator - Frontend Dashboard Controller
 * Handles SPA navigation, Drag-and-Drop Ingestion, Interactive Editing, Analytics, Settings & API Key Validation.
 */

document.addEventListener('DOMContentLoaded', () => {
    // ----------------------------------------------------------------------
    // State Management
    // ----------------------------------------------------------------------
    const state = {
        currentTab: 'dashboard',
        selectedFiles: [],
        currentInvoice: null,
        currency: 'DH',
        analyticsData: null,
        geminiConfigured: false,
    };

    // Helper: Safe URL Reference
    const safeRef = (ref) => encodeURIComponent(ref || '');

    // ----------------------------------------------------------------------
    // DOM Elements
    // ----------------------------------------------------------------------
    const navItems = document.querySelectorAll('.nav-item');
    const tabPanes = document.querySelectorAll('.tab-pane');
    const headerTitle = document.getElementById('header-title');
    const headerSubtitle = document.getElementById('header-subtitle');
    const themeToggleBtn = document.getElementById('theme-toggle-btn');
    const systemStatusText = document.getElementById('system-status-text');

    // Scanner Elements
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('file-input');
    const previewGrid = document.getElementById('preview-grid');
    const clientNameInput = document.getElementById('client-name-input');
    const clientAddressInput = document.getElementById('client-address-input');
    const startScanBtn = document.getElementById('start-scan-btn');
    const clearFilesBtn = document.getElementById('clear-files-btn');
    const progressStepper = document.getElementById('progress-stepper');
    const progressBarFill = document.getElementById('progress-bar-fill');
    const stepperLabel = document.getElementById('stepper-label');
    const resultsCard = document.getElementById('results-card');
    const editClientName = document.getElementById('edit-client-name');
    const editClientAddress = document.getElementById('edit-client-address');
    const editTransactionStatus = document.getElementById('edit-transaction-status');
    const resultsTableBody = document.getElementById('results-table-body');
    const addRowBtn = document.getElementById('add-row-btn');
    const recalculateBtn = document.getElementById('recalculate-btn');
    const previewPdfBtn = document.getElementById('preview-pdf-btn');
    const downloadPdfBtn = document.getElementById('download-pdf-btn');
    const scannerApiWarning = document.getElementById('scanner-api-warning');
    const gotoSettingsBtn = document.getElementById('goto-settings-btn');

    // Archive Elements
    const archiveSearchInput = document.getElementById('archive-search-input');
    const archiveTableBody = document.getElementById('archive-table-body');
    const archiveTotalBadge = document.getElementById('archive-total-badge');

    // Modal Elements
    const pdfModal = document.getElementById('pdf-modal');
    const pdfModalTitle = document.getElementById('pdf-modal-title');
    const pdfModalSubtitle = document.getElementById('pdf-modal-subtitle');
    const pdfModalFrame = document.getElementById('pdf-modal-frame');
    const pdfModalClose = document.getElementById('pdf-modal-close');
    const pdfModalDownload = document.getElementById('pdf-modal-download');
    const modalTabTableBtn = document.getElementById('modal-tab-table-btn');
    const modalTabPdfBtn = document.getElementById('modal-tab-pdf-btn');
    const modalTableView = document.getElementById('modal-table-view');
    const modalPdfView = document.getElementById('modal-pdf-view');
    const modalItemsTbody = document.getElementById('modal-items-tbody');

    // Settings Elements
    const providerGeminiRadio = document.getElementById('provider-gemini');
    const providerDeepseekRadio = document.getElementById('provider-deepseek');
    const geminiConfigPanel = document.getElementById('gemini-config-panel');
    const deepseekConfigPanel = document.getElementById('deepseek-config-panel');

    const settingsCompanyName = document.getElementById('settings-company-name');
    const settingsCompanyAddress = document.getElementById('settings-company-address');
    const settingsCompanyPhone = document.getElementById('settings-company-phone');
    const settingsCompanyEmail = document.getElementById('settings-company-email');
    const settingsCurrency = document.getElementById('settings-currency');

    // Gemini controls
    const settingsGeminiKey = document.getElementById('settings-gemini-key');
    const toggleGeminiKeyBtn = document.getElementById('toggle-gemini-key-btn');
    const testGeminiKeyBtn = document.getElementById('test-gemini-key-btn');
    const refreshGeminiModelsBtn = document.getElementById('refresh-gemini-models-btn');
    const settingsGeminiModel = document.getElementById('settings-gemini-model');
    const geminiStatusBadge = document.getElementById('gemini-status-badge');

    // DeepSeek controls
    const settingsDeepseekKey = document.getElementById('settings-deepseek-key');
    const toggleDeepseekKeyBtn = document.getElementById('toggle-deepseek-key-btn');
    const testDeepseekKeyBtn = document.getElementById('test-deepseek-key-btn');
    const settingsDeepseekModel = document.getElementById('settings-deepseek-model');
    const settingsDeepseekBaseUrl = document.getElementById('settings-deepseek-base-url');
    const deepseekStatusBadge = document.getElementById('deepseek-status-badge');

    const saveSettingsBtn = document.getElementById('save-settings-btn');

    // State additions
    state.aiProvider = 'gemini';
    state.geminiConfigured = false;
    state.deepseekConfigured = false;

    // Helper: Refresh Lucide icons after dynamic DOM changes
    function refreshIcons() {
        if (window.lucide && typeof window.lucide.createIcons === 'function') {
            window.lucide.createIcons();
        }
    }

    // ----------------------------------------------------------------------
    // Toast Notification System
    // ----------------------------------------------------------------------
    function showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        const iconName = type === 'success' ? 'check-circle-2' : type === 'error' ? 'alert-circle' : 'info';
        toast.innerHTML = `<i data-lucide="${iconName}"></i> <span>${message}</span>`;
        container.appendChild(toast);
        refreshIcons();
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }

    // ----------------------------------------------------------------------
    // Theme Management
    // ----------------------------------------------------------------------
    function initTheme() {
        const savedTheme = localStorage.getItem('tyre_theme') || 'dark';
        document.documentElement.setAttribute('data-theme', savedTheme);
        themeToggleBtn.innerHTML = (savedTheme === 'dark') 
            ? '<i data-lucide="sun" id="theme-icon"></i> ' 
            : '<i data-lucide="moon" id="theme-icon"></i> ';
        refreshIcons();
    }

    themeToggleBtn.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme') || 'dark';
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('tyre_theme', next);
        themeToggleBtn.innerHTML = (next === 'dark') 
            ? '<i data-lucide="sun" id="theme-icon"></i> ' 
            : '<i data-lucide="moon" id="theme-icon"></i> ';
        refreshIcons();
    });

    // ----------------------------------------------------------------------
    // Tab Navigation & Real URL Routing (/home, /scanner, /magaza, /archive, /settings)
    // ----------------------------------------------------------------------
    const tabHeaders = {
        dashboard: { title: "Tableau de Bord & Métriques", sub: "Vue d'ensemble de l'activité, chiffre d'affaires et statistiques pneumatiques" },
        scanner: { title: "Numérisation & Consolidation", sub: "Importez vos photos de bons manuscrits et générez vos factures A4" },
        magaza: { title: "Numérisation & Répartition par Dépôt", sub: "Importez vos photos de bons et affectez chaque article aux dépôts (magaza 1, 2, 3, 4)" },
        archive: { title: "Historique des Factures", sub: "Consultez, téléchargez et gérez toutes les factures consolidées" },
        settings: { title: "Paramètres & Configuration", sub: "Personnalisation des mentions légales, fournisseur IA et clés d'accès" },
    };

    const tabUrls = {
        dashboard: '/home',
        scanner: '/scanner',
        magaza: '/magaza',
        archive: '/archive',
        settings: '/settings',
    };

    const urlToTab = {
        '/': 'dashboard',
        '/home': 'dashboard',
        '/dashboard': 'dashboard',
        '/scanner': 'scanner',
        '/scan': 'scanner',
        '/magaza': 'magaza',
        '/depot': 'magaza',
        '/archive': 'archive',
        '/history': 'archive',
        '/historique': 'archive',
        '/settings': 'settings',
        '/parametres': 'settings',
    };

    function switchTab(tabId, updateUrl = true) {
        state.currentTab = tabId;
        navItems.forEach(item => {
            if (item.dataset.tab === tabId) item.classList.add('active');
            else item.classList.remove('active');
        });

        tabPanes.forEach(pane => {
            if (pane.id === `tab-${tabId}`) pane.classList.add('active');
            else pane.classList.remove('active');
        });

        if (tabHeaders[tabId]) {
            headerTitle.textContent = tabHeaders[tabId].title;
            headerSubtitle.textContent = tabHeaders[tabId].sub;
        }

        if (updateUrl) {
            const targetUrl = tabUrls[tabId] || '/home';
            if (window.location.pathname !== targetUrl) {
                window.history.pushState({ tab: tabId }, '', targetUrl);
            }
        }

        if (tabId === 'dashboard') loadAnalytics();
        if (tabId === 'scanner') checkScannerKeyStatus();
        if (tabId === 'magaza') checkMagazaKeyStatus();
        if (tabId === 'archive') loadInvoices();
        if (tabId === 'settings') loadSettings();
    }

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            switchTab(item.dataset.tab, true);
        });
    });

    window.addEventListener('popstate', (e) => {
        const path = window.location.pathname.replace(/\/$/, '') || '/';
        const tab = (e.state && e.state.tab) || urlToTab[path] || 'dashboard';
        switchTab(tab, false);
    });

    if (gotoSettingsBtn) {
        gotoSettingsBtn.addEventListener('click', () => {
            switchTab('settings', true);
        });
    }

    const gotoSettingsBtnMagaza = document.getElementById('goto-settings-btn-magaza');
    if (gotoSettingsBtnMagaza) {
        gotoSettingsBtnMagaza.addEventListener('click', () => {
            switchTab('settings', true);
        });
    }

    function checkScannerKeyStatus() {
        const isConfigured = (state.aiProvider === 'deepseek') ? state.deepseekConfigured : state.geminiConfigured;
        if (!isConfigured) {
            scannerApiWarning.style.display = 'flex';
            const warningText = scannerApiWarning.querySelector('div span:last-child');
            if (warningText) {
                const providerName = state.aiProvider === 'deepseek' ? 'DeepSeek AI' : 'Google Gemini';
                warningText.innerHTML = `<b>Clé d'accès ${providerName} non configurée</b> — Veuillez renseigner votre clé dans l'onglet Paramètres.`;
            }
        } else {
            scannerApiWarning.style.display = 'none';
        }
    }

    function checkMagazaKeyStatus() {
        const isConfigured = (state.aiProvider === 'deepseek') ? state.deepseekConfigured : state.geminiConfigured;
        const magazaApiWarning = document.getElementById('magaza-api-warning');
        if (!magazaApiWarning) return;
        if (!isConfigured) {
            magazaApiWarning.style.display = 'flex';
            const warningText = magazaApiWarning.querySelector('div span:last-child');
            if (warningText) {
                const providerName = state.aiProvider === 'deepseek' ? 'DeepSeek AI' : 'Google Gemini';
                warningText.innerHTML = `<b>Clé d'accès ${providerName} non configurée</b> — Veuillez renseigner votre clé dans l'onglet Paramètres.`;
            }
        } else {
            magazaApiWarning.style.display = 'none';
        }
    }

    // ----------------------------------------------------------------------
    // Analytics Dashboard Logic
    // ----------------------------------------------------------------------
    async function loadAnalytics() {
        try {
            const res = await fetch('/api/analytics');
            if (!res.ok) throw new Error('Erreur chargement analytics');
            const data = await res.json();
            state.analyticsData = data;
            state.currency = data.currency || 'DH';

            const fmt = (n) => Number(n).toLocaleString('fr-FR', { minimumFractionDigits: 2 });

            // Update KPI cards (6 total)
            document.getElementById('kpi-revenue').textContent = `${fmt(data.total_revenue)} ${state.currency}`;
            document.getElementById('kpi-tyres').textContent = `${Number(data.total_tyres).toLocaleString('fr-FR')} pcs`;
            document.getElementById('kpi-invoices').textContent = `${data.total_invoices}`;
            document.getElementById('kpi-avg').textContent = `${fmt(data.avg_ticket)} ${state.currency}`;
            document.getElementById('kpi-max-invoice').textContent = `${fmt(data.max_invoice || 0)} ${state.currency}`;
            document.getElementById('kpi-avg-items').textContent = `${data.avg_items_per_invoice || 0}`;

            // ---- Revenue Trend Sparkline ----
            const trendContainer = document.getElementById('chart-revenue-trend');
            trendContainer.innerHTML = '';
            if (data.revenue_by_day && data.revenue_by_day.length > 0) {
                const days = data.revenue_by_day;
                const maxRev = Math.max(...days.map(d => d.daily_revenue), 1);
                const totalDaysRevenue = days.reduce((s, d) => s + d.daily_revenue, 0);
                const totalDaysQty = days.reduce((s, d) => s + d.daily_qty, 0);

                const barsDiv = document.createElement('div');
                barsDiv.className = 'revenue-trend-bars';
                days.forEach((day, i) => {
                    const heightPct = Math.max((day.daily_revenue / maxRev) * 100, 2);
                    const bar = document.createElement('div');
                    bar.className = 'revenue-trend-bar' + (i === days.length - 1 ? ' highlight' : '');
                    bar.style.height = heightPct + '%';
                    bar.innerHTML = `<div class="revenue-trend-tooltip">${day.date_str}<br>${fmt(day.daily_revenue)} ${state.currency} · ${day.daily_qty} pcs</div>`;
                    barsDiv.appendChild(bar);
                });
                trendContainer.appendChild(barsDiv);

                // Labels
                const labelsDiv = document.createElement('div');
                labelsDiv.className = 'revenue-trend-labels';
                labelsDiv.innerHTML = `<span>${days[0].date_str}</span><span>${days.length} jours</span><span>${days[days.length - 1].date_str}</span>`;
                trendContainer.appendChild(labelsDiv);

                // Summary
                const summaryDiv = document.createElement('div');
                summaryDiv.className = 'revenue-trend-summary';
                summaryDiv.innerHTML = `
                    <span><span class="trend-dot today"></span> Dernier jour</span>
                    <span>Total période : <b>${fmt(totalDaysRevenue)} ${state.currency}</b></span>
                    <span>Pneus : <b>${totalDaysQty} pcs</b></span>
                    <span>Moy./jour : <b>${fmt(totalDaysRevenue / days.length)} ${state.currency}</b></span>
                `;
                trendContainer.appendChild(summaryDiv);
            } else {
                trendContainer.innerHTML = `<div style="text-align:center; color:var(--text-muted); padding:40px 0;">Aucune donnée de tendance disponible.</div>`;
            }



            // ---- Recent Activity (existing, enhanced to 8 rows) ----
            const recentTbody = document.getElementById('recent-invoices-tbody');
            recentTbody.innerHTML = '';
            if (data.recent_invoices && data.recent_invoices.length > 0) {
                data.recent_invoices.forEach(inv => {
                    const tr = document.createElement('tr');
                    const badgeClass = inv.source === 'telegram' ? 'source-telegram' : 'source-web';
                    const badgeText = inv.source === 'telegram' ? 'Telegram' : 'Web UI';
                    tr.innerHTML = `
                        <td><b><code>${inv.invoice_ref}</code></b></td>
                        <td>${inv.client_name}</td>
                        <td>${inv.date_str}</td>
                        <td><b>${inv.total_quantity} pcs</b></td>
                        <td><b>${fmt(inv.grand_total)} ${state.currency}</b></td>
                        <td><span class="table-badge ${badgeClass}">${badgeText}</span></td>
                    `;
                    tr.style.cursor = 'pointer';
                    tr.title = 'Cliquer pour examiner cette facture';
                    tr.addEventListener('click', () => openReviewModal(inv.invoice_ref));
                    recentTbody.appendChild(tr);
                });
            } else {
                recentTbody.innerHTML = `<tr><td colspan="6" style="text-align:center; padding:20px; color:var(--text-muted);">Aucune facture récente.</td></tr>`;
            }
            refreshIcons();

        } catch (err) {
            console.error(err);
            showToast('Impossible de charger les statistiques.', 'error');
        }
    }

    // ----------------------------------------------------------------------
    // Enhanced Image Lightbox Gallery Controller
    // ----------------------------------------------------------------------
    const imageLightbox = document.getElementById('image-lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    const lightboxContent = document.getElementById('lightbox-content');
    const lightboxCaption = document.getElementById('lightbox-caption');
    const lightboxClose = document.getElementById('lightbox-close');
    const lightboxPrev = document.getElementById('lightbox-prev');
    const lightboxNext = document.getElementById('lightbox-next');
    const lightboxCounter = document.getElementById('lightbox-counter');
    const lightboxZoomIn = document.getElementById('lightbox-zoom-in');
    const lightboxZoomOut = document.getElementById('lightbox-zoom-out');
    const lightboxZoomReset = document.getElementById('lightbox-zoom-reset');
    const lightboxRotate = document.getElementById('lightbox-rotate');

    let currentGallery = [];
    let currentGalleryIndex = 0;
    let currentScale = 1.0;
    let currentRotation = 0;

    function updateLightboxTransform() {
        if (!lightboxContent) return;
        lightboxContent.style.transform = `scale(${currentScale}) rotate(${currentRotation}deg)`;
    }

    function renderActiveGalleryImage() {
        if (!imageLightbox || currentGallery.length === 0) return;
        const item = currentGallery[currentGalleryIndex];
        if (!item) return;

        currentScale = 1.0;
        currentRotation = 0;
        updateLightboxTransform();

        lightboxImg.src = item.url;
        if (lightboxCaption) {
            lightboxCaption.textContent = item.caption || item.name || 'Aperçu du bon de commande';
        }

        if (lightboxCounter) {
            lightboxCounter.textContent = `Photo ${currentGalleryIndex + 1} / ${currentGallery.length}`;
        }

        if (lightboxPrev && lightboxNext) {
            lightboxPrev.style.display = currentGallery.length > 1 ? 'flex' : 'none';
            lightboxNext.style.display = currentGallery.length > 1 ? 'flex' : 'none';
        }
        refreshIcons();
    }

    function openGallery(items, startIndex = 0) {
        if (!items || items.length === 0 || !imageLightbox) return;
        currentGallery = items;
        currentGalleryIndex = Math.max(0, Math.min(startIndex, items.length - 1));
        renderActiveGalleryImage();
        imageLightbox.style.display = 'flex';
        refreshIcons();
    }

    function openImageLightbox(src, caption) {
        openGallery([{ url: src, caption: caption, name: 'Aperçu' }], 0);
    }

    function closeImageLightbox() {
        if (!imageLightbox) return;
        imageLightbox.style.display = 'none';
        if (lightboxImg) lightboxImg.src = '';
        currentGallery = [];
        currentScale = 1.0;
        currentRotation = 0;
    }

    if (lightboxPrev) {
        lightboxPrev.addEventListener('click', (e) => {
            e.stopPropagation();
            if (currentGallery.length > 1) {
                currentGalleryIndex = (currentGalleryIndex - 1 + currentGallery.length) % currentGallery.length;
                renderActiveGalleryImage();
            }
        });
    }

    if (lightboxNext) {
        lightboxNext.addEventListener('click', (e) => {
            e.stopPropagation();
            if (currentGallery.length > 1) {
                currentGalleryIndex = (currentGalleryIndex + 1) % currentGallery.length;
                renderActiveGalleryImage();
            }
        });
    }

    if (lightboxZoomIn) {
        lightboxZoomIn.addEventListener('click', (e) => {
            e.stopPropagation();
            currentScale = Math.min(currentScale + 0.25, 3.5);
            updateLightboxTransform();
        });
    }

    if (lightboxZoomOut) {
        lightboxZoomOut.addEventListener('click', (e) => {
            e.stopPropagation();
            currentScale = Math.max(currentScale - 0.25, 0.5);
            updateLightboxTransform();
        });
    }

    if (lightboxZoomReset) {
        lightboxZoomReset.addEventListener('click', (e) => {
            e.stopPropagation();
            currentScale = 1.0;
            currentRotation = 0;
            updateLightboxTransform();
        });
    }

    if (lightboxRotate) {
        lightboxRotate.addEventListener('click', (e) => {
            e.stopPropagation();
            currentRotation = (currentRotation + 90) % 360;
            updateLightboxTransform();
        });
    }

    if (lightboxClose) {
        lightboxClose.addEventListener('click', closeImageLightbox);
    }

    if (imageLightbox) {
        imageLightbox.addEventListener('click', (e) => {
            if (e.target === imageLightbox || e.target.id === 'lightbox-viewport') {
                closeImageLightbox();
            }
        });
    }

    document.addEventListener('keydown', (e) => {
        if (imageLightbox && imageLightbox.style.display === 'flex') {
            if (e.key === 'Escape') {
                closeImageLightbox();
            } else if (e.key === 'ArrowLeft' && currentGallery.length > 1) {
                currentGalleryIndex = (currentGalleryIndex - 1 + currentGallery.length) % currentGallery.length;
                renderActiveGalleryImage();
            } else if (e.key === 'ArrowRight' && currentGallery.length > 1) {
                currentGalleryIndex = (currentGalleryIndex + 1) % currentGallery.length;
                renderActiveGalleryImage();
            } else if (e.key === '+' || e.key === '=') {
                currentScale = Math.min(currentScale + 0.25, 3.5);
                updateLightboxTransform();
            } else if (e.key === '-') {
                currentScale = Math.max(currentScale - 0.25, 0.5);
                updateLightboxTransform();
            } else if (e.key === 'r' || e.key === 'R') {
                currentRotation = (currentRotation + 90) % 360;
                updateLightboxTransform();
            }
        }
    });

    // ----------------------------------------------------------------------
    // Live Receipt Scanner & Drag-and-Drop
    // ----------------------------------------------------------------------
    function updateFilePreviews() {
        previewGrid.innerHTML = '';
        if (state.selectedFiles.length === 0) {
            startScanBtn.disabled = true;
            clearFilesBtn.style.display = 'none';
            return;
        }

        startScanBtn.disabled = false;
        clearFilesBtn.style.display = 'inline-flex';

        state.selectedFiles.forEach((file, index) => {
            const card = document.createElement('div');
            card.className = 'preview-card';
            card.title = 'Cliquer pour agrandir et zoomer sur la photo';
            
            const objectUrl = URL.createObjectURL(file);
            const img = document.createElement('img');
            img.src = objectUrl;

            // Click card to open gallery starting at this index
            card.addEventListener('click', () => {
                const gallery = state.selectedFiles.map(f => ({
                    url: URL.createObjectURL(f),
                    name: f.name,
                    caption: `${f.name} (${(f.size / 1024).toFixed(1)} Ko)`,
                }));
                openGallery(gallery, index);
            });

            const removeBtn = document.createElement('button');
            removeBtn.className = 'preview-remove-btn';
            removeBtn.innerHTML = '&times;';
            removeBtn.title = 'Supprimer cette photo';
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                state.selectedFiles.splice(index, 1);
                updateFilePreviews();
            });

            card.appendChild(img);
            card.appendChild(removeBtn);
            previewGrid.appendChild(card);
        });
        refreshIcons();
    }

    if (dropzone && fileInput) {
        dropzone.addEventListener('click', (e) => {
            if (e.target !== fileInput) fileInput.click();
        });
    }

    fileInput.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        state.selectedFiles = [...state.selectedFiles, ...files];
        fileInput.value = '';
        updateFilePreviews();
    });

    dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('dragover');
    });

    dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('dragover');
    });

    dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('dragover');
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            const files = Array.from(e.dataTransfer.files).filter(f => f.type.startsWith('image/'));
            state.selectedFiles = [...state.selectedFiles, ...files];
            updateFilePreviews();
        }
    });

    clearFilesBtn.addEventListener('click', () => {
        state.selectedFiles = [];
        fileInput.value = '';
        updateFilePreviews();
    });

    // ----------------------------------------------------------------------
    // Scanner Execution with Animated Stepper
    // ----------------------------------------------------------------------
    startScanBtn.addEventListener('click', async () => {
        if (state.selectedFiles.length === 0) return;

        // Prepare UI for scanning
        startScanBtn.disabled = true;
        progressStepper.style.display = 'block';
        resultsCard.style.display = 'none';

        const fileCount = state.selectedFiles.length;
        let elapsed = 0;
        let progressInterval = null;

        // Stage 1: Uploading
        stepperLabel.innerHTML = `<i data-lucide="upload-cloud"></i> Téléversement de ${fileCount} photo(s)...`;
        progressBarFill.style.width = '25%';
        refreshIcons();

        const formData = new FormData();
        state.selectedFiles.forEach(file => {
            formData.append('files', file);
        });
        if (clientNameInput && clientNameInput.value.trim()) {
            formData.append('client_name', clientNameInput.value.trim());
        }
        if (clientAddressInput && clientAddressInput.value.trim()) {
            formData.append('client_address', clientAddressInput.value.trim());
        }

        try {
            // Stage 2: Data Extraction with live timer
            setTimeout(() => {
                stepperLabel.innerHTML = `<i data-lucide="search"></i> Numérisation IA de ${fileCount} reçu(s) (1s)...`;
                progressBarFill.style.width = '45%';
                refreshIcons();

                progressInterval = setInterval(() => {
                    elapsed += 1;
                    const pct = Math.min(45 + elapsed * 5, 88);
                    progressBarFill.style.width = `${pct}%`;
                    stepperLabel.innerHTML = `<i data-lucide="search"></i> Numérisation IA de ${fileCount} reçu(s) (${elapsed}s)...`;
                    refreshIcons();
                }, 1000);
            }, 300);

            const response = await fetch('/api/scan', {
                method: 'POST',
                body: formData,
            });

            if (progressInterval) clearInterval(progressInterval);

            const resData = await response.json();

            if (!response.ok || !resData.success) {
                progressBarFill.style.width = '100%';
                stepperLabel.innerHTML = `<i data-lucide="alert-triangle"></i> Échec de l'extraction`;
                refreshIcons();
                showToast(resData.message || resData.detail || 'Erreur lors du traitement', 'error');
                
                if (resData.message && (resData.message.includes('clé') || resData.message.includes('API'))) {
                    scannerApiWarning.style.display = 'flex';
                }
                return;
            }

            // Stage 3: Consolidation
            stepperLabel.innerHTML = `<i data-lucide="layers"></i> Consolidation & génération de la facture...`;
            progressBarFill.style.width = '92%';
            refreshIcons();

            await new Promise(r => setTimeout(r, 250));

            // Stage 4: Completed
            progressBarFill.style.width = '100%';
            stepperLabel.innerHTML = `<i data-lucide="check-circle-2"></i> Traitement terminé en ${elapsed > 0 ? elapsed + 's' : 'quelques secondes'} !`;
            refreshIcons();

            state.currentInvoice = resData.invoice;
            renderEditableResults(resData.invoice);
            showToast(`Facture ${resData.invoice.invoice_ref} consolidée avec succès !`, 'success');

        } catch (err) {
            if (progressInterval) clearInterval(progressInterval);
            console.error(err);
            showToast(err.message || 'Une erreur est survenue lors du scan.', 'error');
            stepperLabel.innerHTML = `<i data-lucide="x-circle"></i> Échec du traitement.`;
            refreshIcons();
        } finally {
            if (progressInterval) clearInterval(progressInterval);
            startScanBtn.disabled = false;
        }
    });

    // ----------------------------------------------------------------------
    // Standard Tyre Brands List & Parser
    // ----------------------------------------------------------------------
    const TYRE_BRANDS = [
        { code: 'LASSA', label: 'Lassa (L)' },
        { code: 'PETLAS', label: 'Petlas (P)' },
        { code: 'GOODYEAR', label: 'Goodyear (G)' },
        { code: 'STARMAXX', label: 'Starmaxx (St)' },
        { code: 'LAUFENN', label: 'Laufenn (Lf)' },
        { code: 'HANKOOK', label: 'Hankook (Hn)' },
        { code: 'MICHELIN', label: 'Michelin (M)' },
        { code: 'LEAO', label: 'Leao (Le)' },
        { code: 'MONTREAL', label: 'Montreal (Mt)' },
        { code: 'LANDSPIDER', label: 'Landspider (Ls)' },
        { code: 'DELINTE', label: 'Delinte (Dl)' },
        { code: 'TRIANGLE', label: 'Triangle (Tr)' },
        { code: 'ROTALLA', label: 'Rotalla (R)' },
        { code: 'AMINE', label: 'Amine (A)' },
        { code: 'NEXEN', label: 'Nexen (N)' },
        { code: 'BOTO', label: 'Boto (Bt)' },
        { code: 'AUSTONE', label: 'Austone (Au)' },
        { code: 'SEMPERIT', label: 'Semperit (Sp)' },
        { code: 'MOMO', label: 'Momo (Mm)' },
        { code: 'UNIROYAL', label: 'Uniroyal (Un)' },
        { code: 'SEHA', label: 'Seha (Sh)' },
        { code: 'DUNLOP', label: 'Dunlop (D)' },
        { code: 'MILESTONE', label: 'Milestone (Ml)' },
        { code: 'CITY STAR', label: 'City Star (Cs)' },
        { code: 'TIANFU', label: 'Tianfu (Tf)' },
        { code: 'FIRESTONE', label: 'Firestone (F)' },
        { code: 'KLEBER', label: 'Kleber (K)' },
        { code: 'DOUBLE COIN', label: 'Double Coin (Dc)' },
        { code: 'DVR', label: 'DVR' },
        { code: 'TRACMAX', label: 'Tracmax (Tm)' },
        { code: 'APLUS', label: 'Aplus' },
        { code: 'DOUBLESTAR', label: 'Doublestar' },
        { code: 'OVATION', label: 'Ovation' },
        { code: 'PIRELLI', label: 'Pirelli' },
        { code: 'BRIDGESTONE', label: 'Bridgestone' },
        { code: 'CONTINENTAL', label: 'Continental' },
        { code: 'KUMHO', label: 'Kumho' },
        { code: 'YOKOHAMA', label: 'Yokohama' },
        { code: 'TOYO', label: 'Toyo' },
        { code: 'AUTRE', label: 'Sans Marque / Autre' },
    ];

    const BRAND_ALIASES = {
        'L': 'LASSA', 'P': 'PETLAS', 'G': 'GOODYEAR', 'GY': 'GOODYEAR', 'ST': 'STARMAXX',
        'LF': 'LAUFENN', 'HN': 'HANKOOK', 'HK': 'HANKOOK', 'M': 'MICHELIN', 'MI': 'MICHELIN',
        'LE': 'LEAO', 'MT': 'MONTREAL', 'LS': 'LANDSPIDER', 'DL': 'DELINTE', 'TR': 'TRIANGLE',
        'R': 'ROTALLA', 'A': 'AMINE', 'N': 'NEXEN', 'NX': 'NEXEN', 'BT': 'BOTO',
        'AU': 'AUSTONE', 'SP': 'SEMPERIT', 'MM': 'MOMO', 'UN': 'UNIROYAL', 'SH': 'SEHA',
        'D': 'DUNLOP', 'ML': 'MILESTONE', 'CS': 'CITY STAR', 'TF': 'TIANFU', 'F': 'FIRESTONE',
        'FR': 'FIRESTONE', 'K': 'KLEBER', 'KL': 'KLEBER', 'DC': 'DOUBLE COIN', 'DVR': 'DVR',
        'TM': 'TRACMAX'
    };

    function parseDescription(desc = '') {
        const text = (desc || '').trim();
        const parenMatch = text.match(/\(([^)]+)\)/);
        let brand = '';
        let dimension = text;
        if (parenMatch) {
            let rawBrand = parenMatch[1].trim().toUpperCase();
            brand = BRAND_ALIASES[rawBrand] || rawBrand;
            dimension = text.replace(/\([^)]+\)/, '').trim();
        }
        return { dimension, brand };
    }

    function buildBrandSelectHtml(selectedBrand = '') {
        const raw = (selectedBrand || '').trim().toUpperCase();
        const target = BRAND_ALIASES[raw] || raw;
        let options = `<option value="">-- Sans Marque --</option>`;
        let found = false;

        TYRE_BRANDS.forEach(b => {
            const isSelected = (b.code === target);
            if (isSelected) found = true;
            options += `<option value="${b.code}" ${isSelected ? 'selected' : ''}>${b.label}</option>`;
        });

        // If unknown brand not in official tyre catalogue, map to '-- Sans Marque --'
        return `<select class="table-input row-brand">${options}</select>`;
    }

    function appendTableRow(desc = '', qty = 1, price = 0, subtotal = 0, index = null) {
        const tr = document.createElement('tr');
        const idxNum = index || (resultsTableBody.children.length + 1);
        const parsed = parseDescription(desc);

        tr.innerHTML = `
            <td style="width: 4%; text-align: center; color: var(--text-muted); font-weight: bold;">${idxNum}</td>
            <td style="width: 26%;">
                <input type="text" class="table-input row-dim" value="${parsed.dimension}" placeholder="ex: 175/70 R13" />
            </td>
            <td style="width: 22%;">
                ${buildBrandSelectHtml(parsed.brand)}
            </td>
            <td style="width: 13%;">
                <input type="number" class="table-input row-qty" value="${qty}" min="1" step="1" />
            </td>
            <td style="width: 13%;">
                <input type="number" class="table-input row-price" value="${price}" min="0" step="0.5" />
            </td>
            <td style="width: 12%; font-weight: bold;" class="row-subtotal">
                ${Number(subtotal).toFixed(2)} ${state.currency}
            </td>
            <td style="width: 10%; text-align: center; white-space: nowrap;">
                <button type="button" class="btn btn-secondary btn-sm row-up-btn" title="Monter" style="padding: 3px 6px; margin-right: 2px;"><i data-lucide="chevron-up"></i></button>
                <button type="button" class="btn btn-secondary btn-sm row-down-btn" title="Descendre" style="padding: 3px 6px; margin-right: 2px;"><i data-lucide="chevron-down"></i></button>
                <button type="button" class="btn btn-rose btn-sm row-del-btn" title="Supprimer la ligne" style="padding: 3px 6px;"><i data-lucide="trash-2"></i></button>
            </td>
        `;

        const qtyInput = tr.querySelector('.row-qty');
        const priceInput = tr.querySelector('.row-price');
        const subtotalCell = tr.querySelector('.row-subtotal');
        const upBtn = tr.querySelector('.row-up-btn');
        const downBtn = tr.querySelector('.row-down-btn');
        const delBtn = tr.querySelector('.row-del-btn');

        function recalculateRow() {
            const q = parseInt(qtyInput.value) || 0;
            const p = parseFloat(priceInput.value) || 0;
            const sub = (q * p).toFixed(2);
            subtotalCell.textContent = `${sub} ${state.currency}`;
            updateTableTotals();
        }

        qtyInput.addEventListener('input', recalculateRow);
        priceInput.addEventListener('input', recalculateRow);

        upBtn.addEventListener('click', () => {
            const prev = tr.previousElementSibling;
            if (prev) {
                tr.parentNode.insertBefore(tr, prev);
                updateTableTotals();
            }
        });

        downBtn.addEventListener('click', () => {
            const next = tr.nextElementSibling;
            if (next) {
                tr.parentNode.insertBefore(next, tr);
                updateTableTotals();
            }
        });

        delBtn.addEventListener('click', () => {
            tr.remove();
            updateTableTotals();
        });

        resultsTableBody.appendChild(tr);
        refreshIcons();
    }

    function updateTableTotals() {
        const rows = resultsTableBody.querySelectorAll('tr');
        let totalTyres = 0;
        let grandTotal = 0;

        rows.forEach((row, idx) => {
            row.children[0].textContent = idx + 1;
            const qty = parseInt(row.querySelector('.row-qty')?.value) || 0;
            const price = parseFloat(row.querySelector('.row-price')?.value) || 0;
            totalTyres += qty;
            grandTotal += (qty * price);
        });

        document.getElementById('results-total-qty').textContent = `${totalTyres} pcs`;
        document.getElementById('results-grand-total').textContent = `${grandTotal.toFixed(2)} ${state.currency}`;
    }

    // ----------------------------------------------------------------------
    // Render & Edit Results Table
    // ----------------------------------------------------------------------
    function renderEditableResults(invoice) {
        resultsCard.style.display = 'block';
        document.getElementById('results-ref-title').textContent = `${invoice.invoice_ref} (${invoice.client_name})`;
        document.getElementById('results-summary-text').textContent =
            `${invoice.total_quantity} pièces • ${invoice.distinct_items_count} modèles distincts • ${invoice.source_invoices_count} reçu(s) consolidé(s)`;

        if (editClientName) editClientName.value = invoice.client_name || '';
        if (editClientAddress) editClientAddress.value = invoice.client_address || '';
        if (editTransactionStatus) editTransactionStatus.value = invoice.transaction_status || 'En attente';

        resultsTableBody.innerHTML = '';
        if (invoice.items && invoice.items.length > 0) {
            invoice.items.forEach((item, idx) => {
                const descWithBrand = item.brand ? `${item.reference || item.description} (${item.brand})` : item.description;
                appendTableRow(descWithBrand, item.quantity, item.unit_price, item.subtotal, idx + 1);
            });
        }
        updateTableTotals();

        const viewPhotosBtn = document.getElementById('view-source-photos-btn');
        const sourceCountEl = document.getElementById('source-photos-count');
        if (viewPhotosBtn && state.selectedFiles && state.selectedFiles.length > 0) {
            viewPhotosBtn.style.display = 'inline-flex';
            if (sourceCountEl) sourceCountEl.textContent = state.selectedFiles.length;
            viewPhotosBtn.onclick = () => {
                const gallery = state.selectedFiles.map(f => ({
                    url: URL.createObjectURL(f),
                    name: f.name,
                    caption: `${f.name} (${(f.size / 1024).toFixed(1)} Ko)`,
                }));
                openGallery(gallery, 0);
            };
        } else if (viewPhotosBtn) {
            viewPhotosBtn.style.display = 'none';
        }

        refreshIcons();
    }

    addRowBtn.addEventListener('click', () => {
        appendTableRow('175/70 R13 (LASSA)', 4, 450.0, 1800.0);
        updateTableTotals();
    });

    // ----------------------------------------------------------------------
    // Recalculate & Regenerate PDF
    // ----------------------------------------------------------------------
    recalculateBtn.addEventListener('click', async () => {
        if (!state.currentInvoice) return;

        const rows = resultsTableBody.querySelectorAll('tr');
        const items = [];

        rows.forEach(row => {
            const dim = row.querySelector('.row-dim')?.value.trim() || '';
            const brand = row.querySelector('.row-brand')?.value.trim() || '';
            const qty = parseInt(row.querySelector('.row-qty')?.value) || 0;
            const price = parseFloat(row.querySelector('.row-price')?.value) || 0;

            if (dim && qty > 0) {
                let fullDesc = dim;
                if (brand && brand !== 'AUTRE') {
                    fullDesc = `${dim} (${brand})`;
                }
                items.push({
                    description: fullDesc,
                    reference: dim,
                    brand: brand && brand !== 'AUTRE' ? brand : '',
                    quantity: qty,
                    unit_price: price,
                });
            }
        });

        if (items.length === 0) {
            showToast('Veuillez ajouter au moins un article valide.', 'error');
            return;
        }

        try {
            recalculateBtn.disabled = true;
            recalculateBtn.innerHTML = `<i data-lucide="loader-2"></i> Enregistrement...`;
            refreshIcons();

            const payload = {
                client_name: (editClientName ? editClientName.value.trim() : '') || clientNameInput.value.trim() || state.currentInvoice.client_name,
                client_address: (editClientAddress ? editClientAddress.value.trim() : '') || state.currentInvoice.client_address || '',
                transaction_status: (editTransactionStatus ? editTransactionStatus.value.trim() : '') || state.currentInvoice.transaction_status || 'En attente',
                items: items,
            };

            const res = await fetch(`/api/invoices/${safeRef(state.currentInvoice.invoice_ref)}/recalculate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!res.ok) throw new Error('Échec du recalcul de la facture.');

            const data = await res.json();
            state.currentInvoice = data.invoice;
            renderEditableResults(data.invoice);
            showToast('Facture recalculée et PDF mis à jour avec succès !', 'success');

        } catch (err) {
            console.error(err);
            showToast(err.message || 'Erreur lors du recalcul.', 'error');
        } finally {
            recalculateBtn.disabled = false;
            recalculateBtn.innerHTML = `<i data-lucide="save"></i> Enregistrer & Régénérer PDF`;
            refreshIcons();
        }
    });

    previewPdfBtn.addEventListener('click', () => {
        if (state.currentInvoice) {
            openReviewModal(state.currentInvoice.invoice_ref);
        }
    });

    downloadPdfBtn.addEventListener('click', () => {
        if (state.currentInvoice) {
            const clean = state.currentInvoice.invoice_ref.replace('#', '');
            const a = document.createElement('a');
            a.href = `/api/invoices/${safeRef(state.currentInvoice.invoice_ref)}/pdf?download=true`;
            a.download = `Facture_${clean}.pdf`;
            document.body.appendChild(a);
            a.click();
            a.remove();
        }
    });

    // ----------------------------------------------------------------------
    // Magaza (Depot) Scanner & Interactive Editor Controller
    // ----------------------------------------------------------------------
    const dropzoneMagaza = document.getElementById('dropzone-magaza');
    const fileInputMagaza = document.getElementById('file-input-magaza');
    const previewGridMagaza = document.getElementById('preview-grid-magaza');
    const clientNameInputMagaza = document.getElementById('client-name-input-magaza');
    const clientAddressInputMagaza = document.getElementById('client-address-input-magaza');
    const defaultDepotSelect = document.getElementById('default-depot-select');
    const startScanBtnMagaza = document.getElementById('start-scan-btn-magaza');
    const clearFilesBtnMagaza = document.getElementById('clear-files-btn-magaza');
    const progressStepperMagaza = document.getElementById('progress-stepper-magaza');
    const progressBarFillMagaza = document.getElementById('progress-bar-fill-magaza');
    const stepperLabelMagaza = document.getElementById('stepper-label-magaza');
    const resultsCardMagaza = document.getElementById('results-card-magaza');
    const editClientNameMagaza = document.getElementById('edit-client-name-magaza');
    const editClientAddressMagaza = document.getElementById('edit-client-address-magaza');
    const editTransactionStatusMagaza = document.getElementById('edit-transaction-status-magaza');
    const resultsTableBodyMagaza = document.getElementById('results-table-body-magaza');
    const addRowBtnMagaza = document.getElementById('add-row-btn-magaza');
    const recalculateBtnMagaza = document.getElementById('recalculate-btn-magaza');
    const previewPdfBtnMagaza = document.getElementById('preview-pdf-btn-magaza');
    const downloadPdfBtnMagaza = document.getElementById('download-pdf-btn-magaza');

    state.selectedFilesMagaza = [];
    state.currentInvoiceMagaza = null;

    const DEPOT_OPTIONS = ['magaza 1', 'magaza 2', 'magaza 3', 'magaza 4'];

    function buildDepotSelectHtml(selectedDepot = 'magaza 1') {
        const target = (selectedDepot || 'magaza 1').trim().toLowerCase();
        let options = '';
        DEPOT_OPTIONS.forEach(d => {
            const isSelected = (d.toLowerCase() === target);
            options += `<option value="${d}" ${isSelected ? 'selected' : ''}>${d}</option>`;
        });
        return `<select class="table-input row-depot" style="font-weight: 600; color: var(--accent-blue);">${options}</select>`;
    }

    if (dropzoneMagaza && fileInputMagaza) {
        dropzoneMagaza.addEventListener('click', () => fileInputMagaza.click());

        dropzoneMagaza.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropzoneMagaza.classList.add('drag-over');
        });

        dropzoneMagaza.addEventListener('dragleave', () => {
            dropzoneMagaza.classList.remove('drag-over');
        });

        dropzoneMagaza.addEventListener('drop', (e) => {
            e.preventDefault();
            dropzoneMagaza.classList.remove('drag-over');
            handleFilesMagaza(e.dataTransfer.files);
        });

        fileInputMagaza.addEventListener('change', (e) => {
            handleFilesMagaza(e.target.files);
        });
    }

    function handleFilesMagaza(files) {
        const valid = Array.from(files).filter(f => f.type.startsWith('image/'));
        if (valid.length === 0) {
            showToast('Veuillez sélectionner des images valides (PNG, JPG, WebP).', 'warning');
            return;
        }
        state.selectedFilesMagaza = [...state.selectedFilesMagaza, ...valid];
        if (fileInputMagaza) fileInputMagaza.value = '';
        renderPreviewsMagaza();
        updateScanButtonStateMagaza();
    }

    function renderPreviewsMagaza() {
        if (!previewGridMagaza) return;
        previewGridMagaza.innerHTML = '';
        if (state.selectedFilesMagaza.length === 0) {
            if (clearFilesBtnMagaza) clearFilesBtnMagaza.style.display = 'none';
            return;
        }
        if (clearFilesBtnMagaza) clearFilesBtnMagaza.style.display = 'inline-flex';

        state.selectedFilesMagaza.forEach((file, index) => {
            const card = document.createElement('div');
            card.className = 'preview-card';
            card.title = 'Cliquer pour agrandir et zoomer sur la photo';
            card.style.cursor = 'pointer';

            const objectUrl = URL.createObjectURL(file);
            const img = document.createElement('img');
            img.src = objectUrl;

            // Click card to open full lightbox gallery starting at this receipt index
            card.addEventListener('click', () => {
                const gallery = state.selectedFilesMagaza.map(f => ({
                    url: URL.createObjectURL(f),
                    name: f.name,
                    caption: `${f.name} (${(f.size / 1024).toFixed(1)} Ko)`,
                }));
                openGallery(gallery, index);
            });

            const removeBtn = document.createElement('button');
            removeBtn.className = 'preview-remove-btn';
            removeBtn.innerHTML = '&times;';
            removeBtn.title = 'Supprimer cette photo';
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                state.selectedFilesMagaza.splice(index, 1);
                renderPreviewsMagaza();
                updateScanButtonStateMagaza();
            });

            card.appendChild(img);
            card.appendChild(removeBtn);
            previewGridMagaza.appendChild(card);
        });
        refreshIcons();
    }

    function updateScanButtonStateMagaza() {
        if (!startScanBtnMagaza) return;
        const count = state.selectedFilesMagaza.length;
        startScanBtnMagaza.disabled = count === 0;
        const label = startScanBtnMagaza.querySelector('span');
        if (label) {
            label.textContent = count > 0 
                ? `Numériser & Répartir (${count} reçu${count > 1 ? 's' : ''})` 
                : 'Numériser & Générer par Dépôt';
        }
    }

    if (clearFilesBtnMagaza) {
        clearFilesBtnMagaza.addEventListener('click', () => {
            state.selectedFilesMagaza = [];
            renderPreviewsMagaza();
            updateScanButtonStateMagaza();
            if (fileInputMagaza) fileInputMagaza.value = '';
        });
    }

    if (startScanBtnMagaza) {
        startScanBtnMagaza.addEventListener('click', async () => {
            if (state.selectedFilesMagaza.length === 0) return;

            startScanBtnMagaza.disabled = true;
            if (progressStepperMagaza) progressStepperMagaza.style.display = 'block';
            if (resultsCardMagaza) resultsCardMagaza.style.display = 'none';

            const fileCount = state.selectedFilesMagaza.length;
            let elapsed = 0;
            let progressInterval = null;

            if (stepperLabelMagaza) stepperLabelMagaza.innerHTML = `<i data-lucide="upload-cloud"></i> Téléversement de ${fileCount} photo(s)...`;
            if (progressBarFillMagaza) progressBarFillMagaza.style.width = '25%';
            refreshIcons();

            const formData = new FormData();
            state.selectedFilesMagaza.forEach(file => {
                formData.append('files', file);
            });
            if (clientNameInputMagaza && clientNameInputMagaza.value.trim()) {
                formData.append('client_name', clientNameInputMagaza.value.trim());
            }
            if (clientAddressInputMagaza && clientAddressInputMagaza.value.trim()) {
                formData.append('client_address', clientAddressInputMagaza.value.trim());
            }
            const defaultDepot = defaultDepotSelect ? defaultDepotSelect.value : 'magaza 1';
            formData.append('default_depot', defaultDepot);

            try {
                setTimeout(() => {
                    if (stepperLabelMagaza) stepperLabelMagaza.innerHTML = `<i data-lucide="search"></i> Numérisation IA de ${fileCount} reçu(s) (1s)...`;
                    if (progressBarFillMagaza) progressBarFillMagaza.style.width = '45%';
                    refreshIcons();

                    progressInterval = setInterval(() => {
                        elapsed += 1;
                        const pct = Math.min(45 + elapsed * 5, 88);
                        if (progressBarFillMagaza) progressBarFillMagaza.style.width = `${pct}%`;
                        if (stepperLabelMagaza) stepperLabelMagaza.innerHTML = `<i data-lucide="search"></i> Numérisation IA de ${fileCount} reçu(s) (${elapsed}s)...`;
                        refreshIcons();
                    }, 1000);
                }, 300);

                const response = await fetch('/api/scan-magaza', {
                    method: 'POST',
                    body: formData,
                });

                if (progressInterval) clearInterval(progressInterval);

                const resData = await response.json();

                if (!response.ok || !resData.success) {
                    if (progressBarFillMagaza) progressBarFillMagaza.style.width = '100%';
                    if (stepperLabelMagaza) stepperLabelMagaza.innerHTML = `<i data-lucide="alert-triangle"></i> Échec de l'extraction`;
                    refreshIcons();
                    showToast(resData.message || resData.detail || 'Erreur lors du traitement', 'error');

                    const magazaApiWarning = document.getElementById('magaza-api-warning');
                    if (magazaApiWarning && resData.message && (resData.message.includes('clé') || resData.message.includes('API'))) {
                        magazaApiWarning.style.display = 'flex';
                    }
                    return;
                }

                if (stepperLabelMagaza) stepperLabelMagaza.innerHTML = `<i data-lucide="layers"></i> Organisation par magasin & compilation PDF...`;
                if (progressBarFillMagaza) progressBarFillMagaza.style.width = '92%';
                refreshIcons();

                await new Promise(r => setTimeout(r, 250));

                if (progressBarFillMagaza) progressBarFillMagaza.style.width = '100%';
                if (stepperLabelMagaza) stepperLabelMagaza.innerHTML = `<i data-lucide="check-circle-2"></i> Traitement terminé en ${elapsed > 0 ? elapsed + 's' : 'quelques secondes'} !`;
                refreshIcons();

                state.currentInvoiceMagaza = resData.invoice;
                renderEditableMagazaResults(resData.invoice);
                showToast(`Facture par dépôt ${resData.invoice.invoice_ref} générée avec succès !`, 'success');

            } catch (err) {
                if (progressInterval) clearInterval(progressInterval);
                console.error(err);
                showToast(err.message || 'Une erreur est survenue lors du scan.', 'error');
                if (stepperLabelMagaza) stepperLabelMagaza.innerHTML = `<i data-lucide="x-circle"></i> Échec du traitement.`;
                refreshIcons();
            } finally {
                if (progressInterval) clearInterval(progressInterval);
                startScanBtnMagaza.disabled = false;
            }
        });
    }

    function appendMagazaTableRow(desc = '', qty = 1, price = 0, subtotal = 0, depot = 'magaza 1', index = null) {
        if (!resultsTableBodyMagaza) return;
        const tr = document.createElement('tr');
        const idxNum = index || (resultsTableBodyMagaza.children.length + 1);
        const parsed = parseDescription(desc);

        tr.innerHTML = `
            <td style="width: 4%; text-align: center; color: var(--text-muted); font-weight: bold;">${idxNum}</td>
            <td style="width: 22%;">
                <input type="text" class="table-input row-dim" value="${parsed.dimension}" placeholder="ex: 175/70 R13" />
            </td>
            <td style="width: 18%;">
                ${buildBrandSelectHtml(parsed.brand)}
            </td>
            <td style="width: 16%;">
                ${buildDepotSelectHtml(depot)}
            </td>
            <td style="width: 11%;">
                <input type="number" class="table-input row-qty" value="${qty}" min="1" step="1" />
            </td>
            <td style="width: 11%;">
                <input type="number" class="table-input row-price" value="${price}" min="0" step="0.5" />
            </td>
            <td style="width: 9%; font-weight: bold;" class="row-subtotal">
                ${Number(subtotal).toFixed(2)} ${state.currency}
            </td>
            <td style="width: 9%; text-align: center; white-space: nowrap;">
                <button type="button" class="btn btn-secondary btn-sm row-up-btn" title="Monter" style="padding: 3px 6px; margin-right: 2px;"><i data-lucide="chevron-up"></i></button>
                <button type="button" class="btn btn-secondary btn-sm row-down-btn" title="Descendre" style="padding: 3px 6px; margin-right: 2px;"><i data-lucide="chevron-down"></i></button>
                <button type="button" class="btn btn-rose btn-sm row-del-btn" title="Supprimer la ligne" style="padding: 3px 6px;"><i data-lucide="trash-2"></i></button>
            </td>
        `;

        const qtyInput = tr.querySelector('.row-qty');
        const priceInput = tr.querySelector('.row-price');
        const depotSelect = tr.querySelector('.row-depot');
        const subtotalCell = tr.querySelector('.row-subtotal');
        const upBtn = tr.querySelector('.row-up-btn');
        const downBtn = tr.querySelector('.row-down-btn');
        const delBtn = tr.querySelector('.row-del-btn');

        function recalculateRow() {
            const q = parseInt(qtyInput.value) || 0;
            const p = parseFloat(priceInput.value) || 0;
            const sub = (q * p).toFixed(2);
            subtotalCell.textContent = `${sub} ${state.currency}`;
            updateMagazaTableTotals();
        }

        qtyInput.addEventListener('input', recalculateRow);
        priceInput.addEventListener('input', recalculateRow);
        depotSelect.addEventListener('change', updateMagazaTableTotals);

        upBtn.addEventListener('click', () => {
            const prev = tr.previousElementSibling;
            if (prev) {
                tr.parentNode.insertBefore(tr, prev);
                updateMagazaTableTotals();
            }
        });

        downBtn.addEventListener('click', () => {
            const next = tr.nextElementSibling;
            if (next) {
                tr.parentNode.insertBefore(next, tr);
                updateMagazaTableTotals();
            }
        });

        delBtn.addEventListener('click', () => {
            tr.remove();
            updateMagazaTableTotals();
        });

        resultsTableBodyMagaza.appendChild(tr);
        refreshIcons();
    }

    function updateMagazaTableTotals() {
        if (!resultsTableBodyMagaza) return;
        const rows = resultsTableBodyMagaza.querySelectorAll('tr');
        let totalTyres = 0;
        let grandTotal = 0;
        const depotCounts = {};

        rows.forEach((row, idx) => {
            row.children[0].textContent = idx + 1;
            const qty = parseInt(row.querySelector('.row-qty')?.value) || 0;
            const price = parseFloat(row.querySelector('.row-price')?.value) || 0;
            const depot = (row.querySelector('.row-depot')?.value || 'magaza 1').trim();
            totalTyres += qty;
            grandTotal += (qty * price);
            depotCounts[depot] = (depotCounts[depot] || 0) + qty;
        });

        const totalQtyEl = document.getElementById('results-total-qty-magaza');
        const grandTotalEl = document.getElementById('results-grand-total-magaza');
        const pillsContainer = document.getElementById('magaza-pills-container');

        if (totalQtyEl) totalQtyEl.textContent = `${totalTyres} pcs`;
        if (grandTotalEl) grandTotalEl.textContent = `${grandTotal.toFixed(2)} ${state.currency}`;

        if (pillsContainer) {
            pillsContainer.innerHTML = '';
            Object.keys(depotCounts).sort().forEach(d => {
                const pill = document.createElement('span');
                pill.className = 'table-badge source-web';
                pill.style.fontSize = '11px';
                pill.style.padding = '3px 8px';
                pill.textContent = `${d}: ${depotCounts[d]} pcs`;
                pillsContainer.appendChild(pill);
            });
        }
    }

    function renderEditableMagazaResults(invoice) {
        if (!resultsCardMagaza || !resultsTableBodyMagaza) return;
        resultsCardMagaza.style.display = 'block';
        document.getElementById('results-ref-title-magaza').textContent = `${invoice.invoice_ref} (${invoice.client_name || 'Client sans nom'})`;
        document.getElementById('results-summary-text-magaza').textContent =
            `${invoice.total_quantity} pièces • ${invoice.distinct_items_count} modèles distincts • Répartition par Dépôt`;

        if (editClientNameMagaza) editClientNameMagaza.value = invoice.client_name || '';
        if (editClientAddressMagaza) editClientAddressMagaza.value = invoice.client_address || '';
        if (editTransactionStatusMagaza) editTransactionStatusMagaza.value = invoice.transaction_status || 'En attente';

        resultsTableBodyMagaza.innerHTML = '';
        if (invoice.items && invoice.items.length > 0) {
            invoice.items.forEach((item, idx) => {
                const descWithBrand = item.brand ? `${item.reference || item.description} (${item.brand})` : item.description;
                const depotVal = item.depot || 'magaza 1';
                appendMagazaTableRow(descWithBrand, item.quantity, item.unit_price, item.subtotal, depotVal, idx + 1);
            });
        }
        updateMagazaTableTotals();

        const viewPhotosBtnMagaza = document.getElementById('view-source-photos-btn-magaza');
        const sourceCountElMagaza = document.getElementById('source-photos-count-magaza');
        if (viewPhotosBtnMagaza && state.selectedFilesMagaza && state.selectedFilesMagaza.length > 0) {
            viewPhotosBtnMagaza.style.display = 'inline-flex';
            if (sourceCountElMagaza) sourceCountElMagaza.textContent = state.selectedFilesMagaza.length;
            viewPhotosBtnMagaza.onclick = () => {
                const gallery = state.selectedFilesMagaza.map(f => ({
                    url: URL.createObjectURL(f),
                    name: f.name,
                    caption: `${f.name} (${(f.size / 1024).toFixed(1)} Ko)`,
                }));
                openGallery(gallery, 0);
            };
        } else if (viewPhotosBtnMagaza) {
            viewPhotosBtnMagaza.style.display = 'none';
        }

        refreshIcons();
    }

    if (addRowBtnMagaza) {
        addRowBtnMagaza.addEventListener('click', () => {
            const defDepot = defaultDepotSelect ? defaultDepotSelect.value : 'magaza 1';
            appendMagazaTableRow('185/65 R15 (DELINTE)', 4, 480.0, 1920.0, defDepot);
            updateMagazaTableTotals();
        });
    }

    if (recalculateBtnMagaza) {
        recalculateBtnMagaza.addEventListener('click', async () => {
            if (!state.currentInvoiceMagaza) return;

            const rows = resultsTableBodyMagaza.querySelectorAll('tr');
            const items = [];

            rows.forEach(row => {
                const dim = row.querySelector('.row-dim')?.value.trim() || '';
                const brand = row.querySelector('.row-brand')?.value.trim() || '';
                const depot = row.querySelector('.row-depot')?.value.trim() || 'magaza 1';
                const qty = parseInt(row.querySelector('.row-qty')?.value) || 0;
                const price = parseFloat(row.querySelector('.row-price')?.value) || 0;

                if (dim && qty > 0) {
                    let fullDesc = dim;
                    if (brand && brand !== 'AUTRE') {
                        fullDesc = `${dim} (${brand})`;
                    }
                    items.push({
                        description: fullDesc,
                        reference: dim,
                        brand: brand && brand !== 'AUTRE' ? brand : '',
                        depot: depot,
                        quantity: qty,
                        unit_price: price,
                    });
                }
            });

            if (items.length === 0) {
                showToast('Veuillez ajouter au moins un article valide.', 'error');
                return;
            }

            try {
                recalculateBtnMagaza.disabled = true;
                recalculateBtnMagaza.innerHTML = `<i data-lucide="loader-2"></i> Enregistrement...`;
                refreshIcons();

                const payload = {
                    client_name: (editClientNameMagaza ? editClientNameMagaza.value.trim() : '') || (clientNameInputMagaza ? clientNameInputMagaza.value.trim() : '') || state.currentInvoiceMagaza.client_name,
                    client_address: (editClientAddressMagaza ? editClientAddressMagaza.value.trim() : '') || state.currentInvoiceMagaza.client_address || '',
                    transaction_status: (editTransactionStatusMagaza ? editTransactionStatusMagaza.value.trim() : '') || state.currentInvoiceMagaza.transaction_status || 'En attente',
                    items: items,
                };

                const res = await fetch(`/api/invoices/${safeRef(state.currentInvoiceMagaza.invoice_ref)}/recalculate-magaza`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                if (!res.ok) throw new Error('Échec du recalcul de la facture par dépôt.');

                const data = await res.json();
                state.currentInvoiceMagaza = data.invoice;
                renderEditableMagazaResults(data.invoice);
                showToast('Facture par dépôt mise à jour et PDF régénéré avec succès !', 'success');

            } catch (err) {
                console.error(err);
                showToast(err.message || 'Erreur lors du recalcul.', 'error');
            } finally {
                recalculateBtnMagaza.disabled = false;
                recalculateBtnMagaza.innerHTML = `<i data-lucide="save"></i> Enregistrer & Régénérer PDF`;
                refreshIcons();
            }
        });
    }

    if (previewPdfBtnMagaza) {
        previewPdfBtnMagaza.addEventListener('click', () => {
            if (state.currentInvoiceMagaza) {
                openReviewModal(state.currentInvoiceMagaza.invoice_ref, true);
            }
        });
    }

    if (downloadPdfBtnMagaza) {
        downloadPdfBtnMagaza.addEventListener('click', () => {
            if (state.currentInvoiceMagaza) {
                const clean = state.currentInvoiceMagaza.invoice_ref.replace('#', '');
                const a = document.createElement('a');
                a.href = `/api/invoices/${safeRef(state.currentInvoiceMagaza.invoice_ref)}/pdf-magaza?download=true`;
                a.download = `Facture_Magaza_${clean}.pdf`;
                document.body.appendChild(a);
                a.click();
                a.remove();
            }
        });
    }

    // ----------------------------------------------------------------------
    // Invoices Archive Logic
    // ----------------------------------------------------------------------
    async function loadInvoices(searchQuery = '') {
        try {
            const url = searchQuery ? `/api/invoices?search=${encodeURIComponent(searchQuery)}` : '/api/invoices';
            const res = await fetch(url);
            if (!res.ok) throw new Error('Erreur chargement factures');
            const data = await res.json();

            archiveTotalBadge.textContent = `${data.total} factures`;
            archiveTableBody.innerHTML = '';

            if (data.invoices && data.invoices.length > 0) {
                data.invoices.forEach(inv => {
                    const tr = document.createElement('tr');
                    const badgeClass = inv.source === 'telegram' ? 'source-telegram' : 'source-web';
                    const badgeText = inv.source === 'telegram' ? 'Telegram' : 'Web UI';
                    const cleanRef = inv.invoice_ref.replace('#', '');
                    const encodedRef = safeRef(inv.invoice_ref);

                    tr.innerHTML = `
                        <td><b><code>${inv.invoice_ref}</code></b></td>
                        <td><b>${inv.client_name}</b></td>
                        <td>${inv.date_str}</td>
                        <td><b>${inv.total_quantity} pcs</b></td>
                        <td><b>${Number(inv.grand_total).toLocaleString('fr-FR', { minimumFractionDigits: 2 })} ${state.currency}</b></td>
                        <td><span class="table-badge ${badgeClass}">${badgeText}</span></td>
                        <td style="text-align: right; white-space: nowrap;">
                            <button class="btn btn-secondary btn-sm" onclick="window.openReviewModal('${inv.invoice_ref}')" title="Examiner & Voir Facture"><i data-lucide="eye"></i></button>
                            <a href="/api/invoices/${encodedRef}/pdf?download=true" download="Facture_${cleanRef}.pdf" class="btn btn-primary btn-sm" title="Télécharger le PDF"><i data-lucide="download"></i></a>
                            <button class="btn btn-rose btn-sm" onclick="window.deleteInvoice('${inv.invoice_ref}')" title="Supprimer"><i data-lucide="trash-2"></i></button>
                        </td>
                    `;
                    archiveTableBody.appendChild(tr);
                });
                refreshIcons();
            } else {
                archiveTableBody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:30px; color:var(--text-muted);">Aucune facture trouvée.</td></tr>`;
            }

        } catch (err) {
            console.error(err);
            showToast('Erreur lors du chargement des factures.', 'error');
        }
    }

    archiveSearchInput.addEventListener('input', (e) => {
        loadInvoices(e.target.value);
    });

    // ----------------------------------------------------------------------
    // Global Actions (Attached to window for inline onclick)
    // ----------------------------------------------------------------------
    window.openReviewModal = async function(invoiceRef, isMagaza = false) {
        try {
            const encodedRef = safeRef(invoiceRef);
            const res = await fetch(`/api/invoices/${encodedRef}`);
            if (!res.ok) throw new Error('Impossible de charger les détails de la facture.');

            const inv = await res.json();
            const cleanRef = inv.invoice_ref.replace('#', '');
            const useMagaza = isMagaza || (inv.source === 'web_magaza');

            pdfModalTitle.textContent = useMagaza ? `Facture par Dépôt ${inv.invoice_ref}` : `Facture ${inv.invoice_ref}`;
            const clientInfoParts = [inv.client_name];
            if (inv.client_address) clientInfoParts.push(inv.client_address);
            if (inv.transaction_date || inv.date_str) clientInfoParts.push(inv.transaction_date || inv.date_str);
            pdfModalSubtitle.textContent = clientInfoParts.join(' • ');

            document.getElementById('modal-val-client').textContent = inv.client_address ? `${inv.client_name} (${inv.client_address})` : inv.client_name;
            document.getElementById('modal-val-qty').textContent = `${inv.total_quantity} pièces`;
            document.getElementById('modal-val-items').textContent = `${inv.distinct_items_count} modèles`;
            document.getElementById('modal-val-total').textContent = `${Number(inv.grand_total).toLocaleString('fr-FR', { minimumFractionDigits: 2 })} ${state.currency}`;

            modalItemsTbody.innerHTML = '';
            if (inv.items && inv.items.length > 0) {
                inv.items.forEach(item => {
                    const parsed = parseDescription(item.description);
                    const ref = item.reference || parsed.dimension;
                    const brand = item.brand || parsed.brand;
                    const depot = item.depot || '';
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td style="text-align: center; color: var(--text-muted); font-weight: bold;">${item.index_num || item.index || '-'}</td>
                        <td style="font-weight: 700; color: var(--text-primary);">${ref} ${depot ? `<span class="table-badge source-telegram" style="font-size:10px; margin-left:4px;">${depot}</span>` : ''}</td>
                        <td>${brand ? `<span class="table-badge source-web">${brand}</span>` : '<span style="color:var(--text-muted);">-</span>'}</td>
                        <td style="text-align: center; font-weight: 700; color: var(--accent-blue);">${item.quantity} pcs</td>
                        <td style="text-align: right;">${Number(item.unit_price).toFixed(2)} ${state.currency}</td>
                        <td style="text-align: right; font-weight: 700; color: var(--text-primary);">${Number(item.subtotal).toFixed(2)} ${state.currency}</td>
                    `;
                    modalItemsTbody.appendChild(tr);
                });
            } else {
                modalItemsTbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 20px; color: var(--text-muted);">Aucun article dans cette facture.</td></tr>`;
            }

            const pdfUrl = useMagaza ? `/api/invoices/${encodedRef}/pdf-magaza` : `/api/invoices/${encodedRef}/pdf`;
            pdfModalFrame.src = pdfUrl;
            pdfModalDownload.href = `${pdfUrl}?download=true`;
            pdfModalDownload.setAttribute('download', useMagaza ? `Facture_Magaza_${cleanRef}.pdf` : `Facture_${cleanRef}.pdf`);

            showModalTab('table');
            pdfModal.classList.add('active');

        } catch (err) {
            console.error(err);
            showToast('Erreur lors de l’ouverture de la facture.', 'error');
        }
    };

    window.deleteInvoice = async function(ref) {
        if (!confirm(`Êtes-vous sûr de vouloir supprimer définitivement la facture ${ref} ?`)) {
            return;
        }
        try {
            const res = await fetch(`/api/invoices/${safeRef(ref)}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Échec de la suppression.');
            showToast(`Facture ${ref} supprimée.`, 'success');
            loadInvoices(archiveSearchInput.value);
            loadAnalytics();
        } catch (err) {
            console.error(err);
            showToast('Impossible de supprimer la facture.', 'error');
        }
    };

    // ----------------------------------------------------------------------
    // Modal View Toggling & Close Handlers
    // ----------------------------------------------------------------------
    function showModalTab(tab) {
        if (tab === 'table') {
            modalTabTableBtn.classList.add('active');
            modalTabPdfBtn.classList.remove('active');
            modalTableView.style.display = 'block';
            modalPdfView.style.display = 'none';
        } else {
            modalTabPdfBtn.classList.add('active');
            modalTabTableBtn.classList.remove('active');
            modalTableView.style.display = 'none';
            modalPdfView.style.display = 'block';
        }
    }

    modalTabTableBtn.addEventListener('click', () => showModalTab('table'));
    modalTabPdfBtn.addEventListener('click', () => showModalTab('pdf'));

    pdfModalClose.addEventListener('click', () => {
        pdfModal.classList.remove('active');
        pdfModalFrame.src = '';
    });

    pdfModal.addEventListener('click', (e) => {
        if (e.target === pdfModal) {
            pdfModal.classList.remove('active');
            pdfModalFrame.src = '';
        }
    });

    // ----------------------------------------------------------------------
    // Settings Management (Simplified: API Key Input & Business Details)
    // ----------------------------------------------------------------------
    async function loadSettings() {
        try {
            const res = await fetch('/api/settings');
            if (!res.ok) return;
            const data = await res.json();

            // General Business Settings
            if (settingsCompanyName) settingsCompanyName.value = data.company_name || '';
            if (settingsCompanyAddress) settingsCompanyAddress.value = data.company_address || '';
            if (settingsCompanyPhone) settingsCompanyPhone.value = data.company_phone || '';
            if (settingsCompanyEmail) settingsCompanyEmail.value = data.company_email || '';
            if (settingsCurrency) settingsCurrency.value = data.currency || 'DH';

            state.aiProvider = 'gemini';

            // Gemini Key Status
            state.geminiConfigured = data.gemini_api_key_configured;
            if (geminiStatusBadge) {
                if (data.gemini_api_key_configured) {
                    geminiStatusBadge.innerHTML = '<i data-lucide="check-circle-2"></i> Active & Configurée';
                    geminiStatusBadge.className = 'table-badge source-web';
                    if (settingsGeminiKey && !settingsGeminiKey.value && data.gemini_api_key_masked) {
                        settingsGeminiKey.placeholder = `Configurée (${data.gemini_api_key_masked}) — Tapez pour changer`;
                    }
                } else {
                    geminiStatusBadge.innerHTML = '<i data-lucide="alert-circle"></i> Non Configurée';
                    geminiStatusBadge.className = 'table-badge source-telegram';
                    if (settingsGeminiKey) settingsGeminiKey.placeholder = 'AIzaSy... (Saisissez votre clé Gemini)';
                }
            }

            checkScannerKeyStatus();
            checkMagazaKeyStatus();
            refreshIcons();

        } catch (err) {
            console.error(err);
        }
    }

    // Toggle Gemini key visibility
    if (toggleGeminiKeyBtn && settingsGeminiKey) {
        toggleGeminiKeyBtn.addEventListener('click', () => {
            if (settingsGeminiKey.type === 'password') {
                settingsGeminiKey.type = 'text';
                toggleGeminiKeyBtn.innerHTML = '<i data-lucide="eye-off"></i>';
            } else {
                settingsGeminiKey.type = 'password';
                toggleGeminiKeyBtn.innerHTML = '<i data-lucide="eye"></i>';
            }
            refreshIcons();
        });
    }

    // Test Gemini Key
    if (testGeminiKeyBtn) {
        testGeminiKeyBtn.addEventListener('click', async () => {
            const key = settingsGeminiKey ? settingsGeminiKey.value.trim() : '';
            try {
                testGeminiKeyBtn.disabled = true;
                testGeminiKeyBtn.innerHTML = '<i data-lucide="loader-2"></i> Test...';
                refreshIcons();

                const res = await fetch('/api/settings/test-key', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ provider: 'gemini', gemini_api_key: key || undefined }),
                });

                const data = await res.json();
                if (data.valid) {
                    showToast(data.message, 'success');
                    if (geminiStatusBadge) {
                        geminiStatusBadge.innerHTML = '<i data-lucide="check-circle-2"></i> Valide & Connectée';
                        geminiStatusBadge.className = 'table-badge source-web';
                    }
                    state.geminiConfigured = true;
                    checkScannerKeyStatus();
                    checkMagazaKeyStatus();
                } else {
                    showToast(data.message || 'Clé API Gemini invalide', 'error');
                    if (geminiStatusBadge) {
                        geminiStatusBadge.innerHTML = '<i data-lucide="alert-circle"></i> Invalide';
                        geminiStatusBadge.className = 'table-badge source-telegram';
                    }
                }
                refreshIcons();
            } catch (err) {
                console.error(err);
                showToast('Impossible de contacter le serveur de test Gemini.', 'error');
            } finally {
                testGeminiKeyBtn.disabled = false;
                testGeminiKeyBtn.innerHTML = '<i data-lucide="flask-conical"></i> Tester';
                refreshIcons();
            }
        });
    }

    // Save All Settings
    if (saveSettingsBtn) {
        saveSettingsBtn.addEventListener('click', async () => {
            try {
                saveSettingsBtn.disabled = true;
                saveSettingsBtn.innerHTML = '<i data-lucide="loader-2"></i> Enregistrement...';
                refreshIcons();

                const payload = {
                    ai_provider: 'gemini',
                    gemini_model: 'gemini-3.7-flash',
                    company_name: settingsCompanyName ? settingsCompanyName.value.trim() : 'Tous Pneus',
                    company_address: settingsCompanyAddress ? settingsCompanyAddress.value.trim() : undefined,
                    company_phone: settingsCompanyPhone ? settingsCompanyPhone.value.trim() : undefined,
                    company_email: settingsCompanyEmail ? settingsCompanyEmail.value.trim() : undefined,
                    currency: settingsCurrency ? settingsCurrency.value.trim() : 'DH',
                };

                if (settingsGeminiKey && settingsGeminiKey.value.trim()) {
                    payload.gemini_api_key = settingsGeminiKey.value.trim();
                }

                const res = await fetch('/api/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload),
                });

                if (!res.ok) throw new Error('Échec de la sauvegarde');

                const data = await res.json();
                state.aiProvider = 'gemini';
                state.geminiConfigured = data.gemini_api_key_configured;

                showToast('Paramètres et clé API enregistrés avec succès !', 'success');
                if (settingsGeminiKey) settingsGeminiKey.value = '';
                loadSettings();

            } catch (err) {
                console.error(err);
                showToast('Erreur lors de la sauvegarde des paramètres.', 'error');
            } finally {
                saveSettingsBtn.disabled = false;
                saveSettingsBtn.innerHTML = '<i data-lucide="save"></i> Enregistrer les Paramètres';
                refreshIcons();
            }
        });
    }

    // ----------------------------------------------------------------------
    // Initialization
    // ----------------------------------------------------------------------
    initTheme();
    loadSettings();
    const currentPath = window.location.pathname.replace(/\/$/, '') || '/';
    const initialTab = urlToTab[currentPath] || 'dashboard';
    switchTab(initialTab, false);
    refreshIcons();
});
