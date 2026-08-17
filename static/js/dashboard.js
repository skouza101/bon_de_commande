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
    // Tab Navigation
    // ----------------------------------------------------------------------
    const tabHeaders = {
        dashboard: { title: "Tableau de Bord & Métriques", sub: "Vue d'ensemble de l'activité, chiffre d'affaires et statistiques pneumatiques" },
        scanner: { title: "Numérisation & Consolidation", sub: "Importez vos photos de bons manuscrits et générez vos factures A4" },
        archive: { title: "Historique des Factures", sub: "Consultez, téléchargez et gérez toutes les factures consolidées" },
        settings: { title: "Paramètres & Configuration", sub: "Personnalisation des mentions légales, fournisseur IA et clés d'accès" },
    };

    function switchTab(tabId) {
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

        if (tabId === 'dashboard') loadAnalytics();
        if (tabId === 'scanner') checkScannerKeyStatus();
        if (tabId === 'archive') loadInvoices();
        if (tabId === 'settings') loadSettings();
    }

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            switchTab(item.dataset.tab);
        });
    });

    if (gotoSettingsBtn) {
        gotoSettingsBtn.addEventListener('click', () => {
            switchTab('settings');
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

    // Image Lightbox Elements
    const imageLightbox = document.getElementById('image-lightbox');
    const lightboxImg = document.getElementById('lightbox-img');
    const lightboxCaption = document.getElementById('lightbox-caption');
    const lightboxClose = document.getElementById('lightbox-close');

    function openImageLightbox(src, caption) {
        if (!imageLightbox || !lightboxImg) return;
        lightboxImg.src = src;
        if (lightboxCaption) {
            lightboxCaption.textContent = caption || 'Aperçu du bon de commande';
        }
        imageLightbox.style.display = 'flex';
    }

    function closeImageLightbox() {
        if (!imageLightbox) return;
        imageLightbox.style.display = 'none';
        if (lightboxImg) lightboxImg.src = '';
    }

    if (lightboxClose) {
        lightboxClose.addEventListener('click', closeImageLightbox);
    }
    if (imageLightbox) {
        imageLightbox.addEventListener('click', (e) => {
            if (e.target === imageLightbox) closeImageLightbox();
        });
    }
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && imageLightbox && imageLightbox.style.display === 'flex') {
            closeImageLightbox();
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
            card.title = 'Cliquer pour agrandir la photo';
            
            const objectUrl = URL.createObjectURL(file);
            const img = document.createElement('img');
            img.src = objectUrl;

            // Click card to open full lightbox preview
            card.addEventListener('click', () => {
                openImageLightbox(objectUrl, `${file.name} (${(file.size / 1024).toFixed(1)} Ko)`);
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

    fileInput.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        state.selectedFiles = [...state.selectedFiles, ...files];
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

        // Stage 1: Uploading
        stepperLabel.innerHTML = `<i data-lucide="upload-cloud"></i> Téléversement de ${state.selectedFiles.length} photo(s)...`;
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
            // Stage 2: Data Extraction
            setTimeout(() => {
                stepperLabel.innerHTML = `<i data-lucide="search"></i> Numérisation et lecture des données manuscrites...`;
                progressBarFill.style.width = '60%';
                refreshIcons();
            }, 500);

            const response = await fetch('/api/scan', {
                method: 'POST',
                body: formData,
            });

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
            progressBarFill.style.width = '90%';
            refreshIcons();

            await new Promise(r => setTimeout(r, 400));

            // Stage 4: Completed
            progressBarFill.style.width = '100%';
            stepperLabel.innerHTML = `<i data-lucide="check-circle-2"></i> Traitement terminé avec succès !`;
            refreshIcons();

            state.currentInvoice = resData.invoice;
            renderEditableResults(resData.invoice);
            showToast(`Facture ${resData.invoice.invoice_ref} consolidée avec succès !`, 'success');

        } catch (err) {
            console.error(err);
            showToast(err.message || 'Une erreur est survenue lors du scan.', 'error');
            stepperLabel.innerHTML = `<i data-lucide="x-circle"></i> Échec du traitement.`;
            refreshIcons();
        } finally {
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
            <td style="width: 5%; text-align: center; color: var(--text-muted); font-weight: bold;">${idxNum}</td>
            <td style="width: 28%;">
                <input type="text" class="table-input row-dim" value="${parsed.dimension}" placeholder="ex: 175/70 R13" />
            </td>
            <td style="width: 24%;">
                ${buildBrandSelectHtml(parsed.brand)}
            </td>
            <td style="width: 13%;">
                <input type="number" class="table-input row-qty" value="${qty}" min="1" step="1" />
            </td>
            <td style="width: 14%;">
                <input type="number" class="table-input row-price" value="${price}" min="0" step="0.5" />
            </td>
            <td style="width: 11%; font-weight: bold;" class="row-subtotal">
                ${Number(subtotal).toFixed(2)} ${state.currency}
            </td>
            <td style="width: 5%; text-align: center;">
                <button class="btn btn-rose btn-sm row-del-btn" title="Supprimer la ligne"><i data-lucide="trash-2"></i></button>
            </td>
        `;

        const qtyInput = tr.querySelector('.row-qty');
        const priceInput = tr.querySelector('.row-price');
        const subtotalCell = tr.querySelector('.row-subtotal');
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
    window.openReviewModal = async function(invoiceRef) {
        try {
            const encodedRef = safeRef(invoiceRef);
            const res = await fetch(`/api/invoices/${encodedRef}`);
            if (!res.ok) throw new Error('Impossible de charger les détails de la facture.');

            const inv = await res.json();
            const cleanRef = inv.invoice_ref.replace('#', '');

            pdfModalTitle.textContent = `Facture ${inv.invoice_ref}`;
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
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td style="text-align: center; color: var(--text-muted); font-weight: bold;">${item.index_num || item.index || '-'}</td>
                        <td style="font-weight: 700; color: var(--text-primary);">${ref}</td>
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

            const pdfUrl = `/api/invoices/${encodedRef}/pdf`;
            pdfModalFrame.src = pdfUrl;
            pdfModalDownload.href = `${pdfUrl}?download=true`;
            pdfModalDownload.setAttribute('download', `Facture_${cleanRef}.pdf`);

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
    // AI Provider Switcher
    // ----------------------------------------------------------------------
    function updateProviderPanels() {
        const isDeepseek = providerDeepseekRadio && providerDeepseekRadio.checked;
        state.aiProvider = isDeepseek ? 'deepseek' : 'gemini';

        if (geminiConfigPanel && deepseekConfigPanel) {
            geminiConfigPanel.style.display = isDeepseek ? 'none' : 'flex';
            deepseekConfigPanel.style.display = isDeepseek ? 'flex' : 'none';
        }

        const geminiLabel = document.getElementById('provider-gemini-label');
        const deepseekLabel = document.getElementById('provider-deepseek-label');
        if (geminiLabel && deepseekLabel) {
            if (isDeepseek) {
                geminiLabel.classList.remove('active');
                deepseekLabel.classList.add('active');
            } else {
                geminiLabel.classList.add('active');
                deepseekLabel.classList.remove('active');
            }
        }

        checkScannerKeyStatus();
    }

    if (providerGeminiRadio && providerDeepseekRadio) {
        providerGeminiRadio.addEventListener('change', updateProviderPanels);
        providerDeepseekRadio.addEventListener('change', updateProviderPanels);
    }

    // ----------------------------------------------------------------------
    // Settings Management
    // ----------------------------------------------------------------------
    function populateGeminiModels(modelsList, selectedModel) {
        if (!settingsGeminiModel || !modelsList || modelsList.length === 0) return;

        settingsGeminiModel.innerHTML = '';
        const targetModel = (selectedModel || 'gemini-2.5-flash').replace('models/', '').trim();

        let found = false;
        modelsList.forEach(m => {
            const opt = document.createElement('option');
            opt.value = m.id;
            const badge = m.is_flash ? '⚡ Rapide' : '🧠 Précis';
            opt.textContent = `${m.name} (${m.id}) — ${badge}`;
            if (m.id === targetModel) {
                opt.selected = true;
                found = true;
            }
            settingsGeminiModel.appendChild(opt);
        });

        if (!found && targetModel) {
            const customOpt = document.createElement('option');
            customOpt.value = targetModel;
            customOpt.textContent = `${targetModel} (Actuel)`;
            customOpt.selected = true;
            settingsGeminiModel.appendChild(customOpt);
        }
    }

    async function loadGeminiModels(apiKey = '') {
        try {
            if (refreshGeminiModelsBtn) refreshGeminiModelsBtn.disabled = true;
            const url = '/api/settings/models';
            const res = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ provider: 'gemini', gemini_api_key: apiKey || undefined }),
            });
            if (res.ok) {
                const data = await res.json();
                if (data.models) {
                    populateGeminiModels(data.models, data.selected);
                }
            }
        } catch (err) {
            console.error(err);
        } finally {
            if (refreshGeminiModelsBtn) refreshGeminiModelsBtn.disabled = false;
        }
    }

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

            // Provider selection
            state.aiProvider = data.ai_provider || 'gemini';
            if (state.aiProvider === 'deepseek') {
                if (providerDeepseekRadio) providerDeepseekRadio.checked = true;
            } else {
                if (providerGeminiRadio) providerGeminiRadio.checked = true;
            }
            updateProviderPanels();

            // Gemini Settings
            state.geminiConfigured = data.gemini_api_key_configured;
            if (data.gemini_api_key_configured) {
                geminiStatusBadge.innerHTML = '<i data-lucide="check-circle-2"></i> Active & Configurée';
                geminiStatusBadge.className = 'table-badge source-web';
                if (!settingsGeminiKey.value && data.gemini_api_key_masked) {
                    settingsGeminiKey.placeholder = `Configurée (${data.gemini_api_key_masked}) — Tapez pour changer`;
                }
            } else {
                geminiStatusBadge.innerHTML = '<i data-lucide="alert-circle"></i> Non Configurée';
                geminiStatusBadge.className = 'table-badge source-telegram';
                settingsGeminiKey.placeholder = 'AIzaSy... (Saisissez votre clé Gemini)';
            }

            // DeepSeek Settings
            state.deepseekConfigured = data.deepseek_api_key_configured;
            if (data.deepseek_api_key_configured) {
                deepseekStatusBadge.innerHTML = '<i data-lucide="check-circle-2"></i> Active & Configurée';
                deepseekStatusBadge.className = 'table-badge source-web';
                if (!settingsDeepseekKey.value && data.deepseek_api_key_masked) {
                    settingsDeepseekKey.placeholder = `Configurée (${data.deepseek_api_key_masked}) — Tapez pour changer`;
                }
            } else {
                deepseekStatusBadge.innerHTML = '<i data-lucide="alert-circle"></i> Non Configurée';
                deepseekStatusBadge.className = 'table-badge source-telegram';
                settingsDeepseekKey.placeholder = 'sk-... (Saisissez votre clé DeepSeek)';
            }

            if (settingsDeepseekModel && data.deepseek_model) {
                settingsDeepseekModel.value = data.deepseek_model;
            }
            if (settingsDeepseekBaseUrl && data.deepseek_base_url) {
                settingsDeepseekBaseUrl.value = data.deepseek_base_url;
            }

            // Load Gemini models
            await loadGeminiModels();
            if (settingsGeminiModel && data.gemini_model) {
                settingsGeminiModel.value = data.gemini_model.replace('models/', '').trim();
            }

            checkScannerKeyStatus();
            refreshIcons();

        } catch (err) {
            console.error(err);
        }
    }

    if (refreshGeminiModelsBtn) {
        refreshGeminiModelsBtn.addEventListener('click', async () => {
            showToast('Détection des moteurs Gemini supportés...', 'info');
            await loadGeminiModels(settingsGeminiKey.value.trim());
            showToast('Liste des modèles Gemini actualisée avec succès !', 'success');
        });
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

    // Toggle DeepSeek key visibility
    if (toggleDeepseekKeyBtn && settingsDeepseekKey) {
        toggleDeepseekKeyBtn.addEventListener('click', () => {
            if (settingsDeepseekKey.type === 'password') {
                settingsDeepseekKey.type = 'text';
                toggleDeepseekKeyBtn.innerHTML = '<i data-lucide="eye-off"></i>';
            } else {
                settingsDeepseekKey.type = 'password';
                toggleDeepseekKeyBtn.innerHTML = '<i data-lucide="eye"></i>';
            }
            refreshIcons();
        });
    }

    // Preset Buttons for OpenRouter and DeepSeek
    const presetOpenrouterBtn = document.getElementById('preset-openrouter-btn');
    const presetDeepseekBtn = document.getElementById('preset-deepseek-btn');

    if (presetOpenrouterBtn) {
        presetOpenrouterBtn.addEventListener('click', () => {
            if (settingsDeepseekBaseUrl) settingsDeepseekBaseUrl.value = 'https://openrouter.ai/api/v1';
            if (settingsDeepseekModel) settingsDeepseekModel.value = 'deepseek/deepseek-v4-flash-0731';
            if (settingsDeepseekKey && !settingsDeepseekKey.value) {
                settingsDeepseekKey.placeholder = 'sk-or-v1-... (Collez votre clé OpenRouter)';
            }
            showToast('Preset OpenRouter appliqué ! Modèle gratuit pré-rempli.', 'info');
        });
    }

    if (presetDeepseekBtn) {
        presetDeepseekBtn.addEventListener('click', () => {
            if (settingsDeepseekBaseUrl) settingsDeepseekBaseUrl.value = 'https://api.deepseek.com';
            if (settingsDeepseekModel) settingsDeepseekModel.value = 'deepseek-chat';
            if (settingsDeepseekKey && !settingsDeepseekKey.value) {
                settingsDeepseekKey.placeholder = 'sk-... (Collez votre clé DeepSeek)';
            }
            showToast('Preset DeepSeek Officiel appliqué !', 'info');
        });
    }

    // Test Gemini Key
    if (testGeminiKeyBtn) {
        testGeminiKeyBtn.addEventListener('click', async () => {
            const key = settingsGeminiKey.value.trim();
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
                    geminiStatusBadge.innerHTML = '<i data-lucide="check-circle-2"></i> Valide & Connectée';
                    geminiStatusBadge.className = 'table-badge source-web';
                    if (data.supported_models) {
                        populateGeminiModels(data.supported_models, data.model);
                    }
                    state.geminiConfigured = true;
                    checkScannerKeyStatus();
                } else {
                    showToast(data.message || 'Clé API Gemini invalide', 'error');
                    geminiStatusBadge.innerHTML = '<i data-lucide="alert-circle"></i> Invalide';
                    geminiStatusBadge.className = 'table-badge source-telegram';
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

    // Test DeepSeek / OpenRouter Key
    if (testDeepseekKeyBtn) {
        testDeepseekKeyBtn.addEventListener('click', async () => {
            const key = settingsDeepseekKey ? settingsDeepseekKey.value.trim() : '';
            const baseUrl = (settingsDeepseekBaseUrl && settingsDeepseekBaseUrl.value) ? settingsDeepseekBaseUrl.value.trim() : 'https://openrouter.ai/api/v1';
            const model = (settingsDeepseekModel && settingsDeepseekModel.value) ? settingsDeepseekModel.value.trim() : 'deepseek/deepseek-v4-flash-0731';

            try {
                testDeepseekKeyBtn.disabled = true;
                testDeepseekKeyBtn.innerHTML = '<i data-lucide="loader-2"></i> Test...';
                refreshIcons();

                const res = await fetch('/api/settings/test-key', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        provider: 'deepseek',
                        deepseek_api_key: key || undefined,
                        deepseek_base_url: baseUrl || 'https://openrouter.ai/api/v1',
                        deepseek_model: model || 'deepseek/deepseek-v4-flash-0731',
                    }),
                });

                const data = await res.json();
                if (data.valid) {
                    showToast(data.message, 'success');
                    deepseekStatusBadge.innerHTML = '<i data-lucide="check-circle-2"></i> Valide & Connectée';
                    deepseekStatusBadge.className = 'table-badge source-web';
                    state.deepseekConfigured = true;
                    checkScannerKeyStatus();
                } else {
                    showToast(data.message || 'Échec de connexion DeepSeek', 'error');
                    deepseekStatusBadge.innerHTML = '<i data-lucide="alert-circle"></i> Invalide';
                    deepseekStatusBadge.className = 'table-badge source-telegram';
                }
                refreshIcons();
            } catch (err) {
                console.error(err);
                showToast('Impossible de contacter le serveur de test DeepSeek.', 'error');
            } finally {
                testDeepseekKeyBtn.disabled = false;
                testDeepseekKeyBtn.innerHTML = '<i data-lucide="flask-conical"></i> Tester';
                refreshIcons();
            }
        });
    }

    // Save All Settings
    saveSettingsBtn.addEventListener('click', async () => {
        try {
            saveSettingsBtn.disabled = true;
            saveSettingsBtn.innerHTML = '<i data-lucide="loader-2"></i> Enregistrement...';
            refreshIcons();

            const activeProvider = (providerDeepseekRadio && providerDeepseekRadio.checked) ? 'deepseek' : 'gemini';

            const payload = {
                ai_provider: activeProvider,
                company_name: settingsCompanyName.value.trim(),
                company_address: settingsCompanyAddress ? settingsCompanyAddress.value.trim() : undefined,
                company_phone: settingsCompanyPhone ? settingsCompanyPhone.value.trim() : undefined,
                company_email: settingsCompanyEmail ? settingsCompanyEmail.value.trim() : undefined,
                currency: settingsCurrency.value.trim(),
                gemini_model: settingsGeminiModel ? settingsGeminiModel.value.trim() : undefined,
                deepseek_model: settingsDeepseekModel ? settingsDeepseekModel.value.trim() : undefined,
                deepseek_base_url: settingsDeepseekBaseUrl ? settingsDeepseekBaseUrl.value.trim() : undefined,
            };

            if (settingsGeminiKey && settingsGeminiKey.value.trim()) {
                payload.gemini_api_key = settingsGeminiKey.value.trim();
            }
            if (settingsDeepseekKey && settingsDeepseekKey.value.trim()) {
                payload.deepseek_api_key = settingsDeepseekKey.value.trim();
            }

            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!res.ok) throw new Error('Échec de la sauvegarde');

            const data = await res.json();
            state.aiProvider = data.ai_provider;
            state.geminiConfigured = data.gemini_api_key_configured;
            state.deepseekConfigured = data.deepseek_api_key_configured;

            showToast('Paramètres et configuration enregistrés avec succès !', 'success');
            loadSettings();

        } catch (err) {
            console.error(err);
            showToast('Erreur lors de la sauvegarde des paramètres.', 'error');
        } finally {
            saveSettingsBtn.disabled = false;
            saveSettingsBtn.innerHTML = '<i data-lucide="save"></i> Enregistrer les Modifications';
            refreshIcons();
        }
    });

    // ----------------------------------------------------------------------
    // Initialization
    // ----------------------------------------------------------------------
    initTheme();
    loadAnalytics();
    loadSettings();
    refreshIcons();
});
