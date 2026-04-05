
import './style.css';

// GPR Analytics — Main Application Logic
// Industrial-scientific interface interactions

document.addEventListener('DOMContentLoaded', () => {
    // Form Elements
    const form = document.getElementById('upload-form');
    const submitBtn = document.getElementById('submit-btn');
    const btnText = document.getElementById('btn-text');
    const btnSpinner = document.getElementById('btn-spinner');
    const btnProgress = document.getElementById('btn-progress');
    const errorMessage = document.getElementById('error-message');
    const errorText = errorMessage.querySelector('.error-text');

    // File Upload Zones
    const kmlZone = document.getElementById('kml-zone');
    const gprZone = document.getElementById('gpr-zone');
    const kmlInput = document.getElementById('kml_file');
    const gprInput = document.getElementById('gpr_file');
    const kmlFilename = document.getElementById('kml-filename');
    const gprFilename = document.getElementById('gpr-filename');

    // Result Elements
    const resultsSection = document.getElementById('results-section');
    const summaryCards = document.getElementById('summary-cards');
    const chartContainer = document.getElementById('chart-container');
    const mapContainer = document.getElementById('map-container');
    const resultMap = document.getElementById('result-map');
    const resultChart = document.getElementById('result-chart');
    const sumTraces = document.getElementById('sum-traces');
    const sumDist = document.getElementById('sum-dist');
    const sumDistFt = document.getElementById('sum-dist-ft');
    const tracesBadge = document.getElementById('traces-badge');
    const statsMean = document.getElementById('stats-mean');
    const statsStd = document.getElementById('stats-std');

    const distContainer = document.getElementById('dist-container');
    const exportContainer = document.getElementById('export-container');
    const resultDist = document.getElementById('result-dist');

    const downloadProfile = document.getElementById('download-profile');
    const downloadMap = document.getElementById('download-map');
    const downloadDist = document.getElementById('download-dist');
    const downloadExcel = document.getElementById('download-excel');

    // Parameter Inputs
    const offsetInput = document.getElementById('antenna_offset');
    const offsetSlider = document.getElementById('offset-slider');

    // Latency Display
    const latencyDisplay = document.getElementById('latency');

    // Layer selection elements
    const layerSelection = document.getElementById('layer-selection');
    const layerGrid = document.getElementById('layer-grid');
    const selectedColumnInput = document.getElementById('selected_column');

    // Initialize
    resultsSection.classList.add('hidden');
    hideResults();
    initDragDrop();
    initParamSync();
    startLatencySimulation();
    initCoordinateTracking();

    // File Upload Handling
    kmlInput.addEventListener('change', (e) => handleFileSelect(e, kmlZone, kmlFilename, 'KML'));
    gprInput.addEventListener('change', (e) => {
        handleFileSelect(e, gprZone, gprFilename, 'OUT');
        if (e.target.files[0]) {
            fetchPreview(e.target.files[0]);
        }
    });

    // Form Submission
    form.addEventListener('submit', handleSubmit);

    async function fetchPreview(file) {
        layerSelection.classList.remove('hidden');
        layerGrid.innerHTML = `
            <div class="loading-state" style="grid-column: 1/-1; padding: 40px; text-align: center; color: var(--text-tertiary); font-family: var(--font-mono); font-size: 0.75rem;">
                SCANNING DATA LAYERS...
            </div>
        `;

        try {
            const formData = new FormData();
            formData.append('gpr_file', file);

            const response = await fetch('/preview', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Preview scan failed');
            const data = await response.json();
            renderLayerGrid(data.columns);
        } catch (err) {
            layerGrid.innerHTML = `<div class="error-text" style="grid-column: 1/-1; color: var(--signal-red);">Scan Error: ${err.message}</div>`;
        }
    }

    function renderLayerGrid(columns) {
        layerGrid.innerHTML = '';
        columns.forEach(col => {
            const card = document.createElement('div');
            card.className = `layer-card ${col.is_empty ? 'empty' : ''} ${col.index === parseInt(selectedColumnInput.value) ? 'active' : ''}`;
            
            // Create SVG Sparkline
            const sparkline = createSparkline(col.data);
            
            card.innerHTML = `
                <div class="layer-info">
                    <span class="layer-name">${col.name}</span>
                    <span class="layer-stats">${col.mean.toFixed(2)}" avg</span>
                </div>
                <div class="layer-preview">${sparkline}</div>
            `;

            if (!col.is_empty) {
                card.onclick = () => {
                    document.querySelectorAll('.layer-card').forEach(c => c.classList.remove('active'));
                    card.classList.add('active');
                    selectedColumnInput.value = col.index;
                };
            }

            layerGrid.appendChild(card);
        });
    }

    function createSparkline(points) {
        if (!points || points.length === 0) return '';
        const min = Math.min(...points);
        const max = Math.max(...points);
        const range = max - min || 1;
        
        const width = 200;
        const height = 40;
        const mappedPoints = points.map((p, i) => {
            const x = (i / (points.length - 1)) * width;
            const y = height - ((p - min) / range) * height;
            return `${x},${y}`;
        }).join(' ');

        return `
            <svg class="sparkline-svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none">
                <polyline class="sparkline-path" points="${mappedPoints}" />
            </svg>
        `;
    }

    // Handle File Selection
    function handleFileSelect(e, zone, filenameDisplay, type) {
        const file = e.target.files[0];
        if (file) {
            zone.classList.add('has-file');
            filenameDisplay.textContent = file.name;
            filenameDisplay.style.display = 'block';

            // Visual feedback
            zone.style.transform = 'scale(0.98)';
            setTimeout(() => {
                zone.style.transform = '';
            }, 150);
        } else {
            zone.classList.remove('has-file');
            filenameDisplay.textContent = '';
        }
    }

    // Drag and Drop Initialization
    function initDragDrop() {
        const zones = [kmlZone, gprZone];
        const inputs = { [kmlZone.id]: kmlInput, [gprZone.id]: gprInput };
        const displays = { [kmlZone.id]: kmlFilename, [gprZone.id]: gprFilename };
        const types = { [kmlZone.id]: 'KML', [gprZone.id]: 'OUT' };

        zones.forEach(zone => {
            zone.addEventListener('dragover', (e) => {
                e.preventDefault();
                zone.classList.add('drag-active');
            });

            zone.addEventListener('dragleave', () => {
                zone.classList.remove('drag-active');
            });

            zone.addEventListener('drop', (e) => {
                e.preventDefault();
                zone.classList.remove('drag-active');

                const files = e.dataTransfer.files;
                if (files.length > 0) {
                    const input = inputs[zone.id];
                    const dt = new DataTransfer();
                    dt.items.add(files[0]);
                    input.files = dt.files;

                    // Trigger change event
                    const event = new Event('change', { bubbles: true });
                    input.dispatchEvent(event);
                }
            });
        });
    }

    // Parameter Sync (Number input <-> Slider)
    function initParamSync() {
        offsetSlider.addEventListener('input', () => {
            offsetInput.value = offsetSlider.value;
        });

        offsetInput.addEventListener('input', () => {
            offsetSlider.value = offsetInput.value;
        });
    }

    // Form Submission Handler
    async function handleSubmit(e) {
        e.preventDefault();

        // Reset states
        errorMessage.classList.add('hidden');
        errorText.textContent = '';
        hideResults();

        // Loading UI
        submitBtn.disabled = true;
        btnText.textContent = 'PROCESSING DATA STREAM...';
        btnSpinner.classList.add('active');
        btnProgress.style.width = '0%';

        // Simulate progress
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += Math.random() * 15;
            if (progress > 90) progress = 90;
            btnProgress.style.width = `${progress}%`;
        }, 200);

        try {
            const formData = new FormData(form);

            const response = await fetch('/analyze', {
                method: 'POST',
                body: formData
            });

            clearInterval(progressInterval);
            btnProgress.style.width = '100%';

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `Server error: ${response.status}`);
            }

            const data = await response.json();

            // Populate and show results
            populateResults(data);
            showResults();

        } catch (error) {
            clearInterval(progressInterval);
            console.error('Analysis failed:', error);
            errorText.textContent = error.message;
            errorMessage.classList.remove('hidden');
        } finally {
            // Restore UI
            setTimeout(() => {
                submitBtn.disabled = false;
                btnText.textContent = 'INITIATE ANALYSIS';
                btnSpinner.classList.remove('active');
                btnProgress.style.width = '0%';
            }, 500);
        }
    }

    // Populate Results Data
    function populateResults(data) {
        // Traces
        const traces = data.data_summary.traces_parsed;
        sumTraces.textContent = traces.toLocaleString();

        // Update badge based on trace count
        if (traces > 10000) {
            tracesBadge.textContent = 'HIGH';
            tracesBadge.style.color = 'var(--signal-blue)';
            tracesBadge.style.borderColor = 'rgba(59, 130, 246, 0.3)';
            tracesBadge.style.background = 'rgba(59, 130, 246, 0.1)';
        }

        // Distance
        const totalFeet = data.data_summary.total_distance_ft;
        const mi = Math.floor(totalFeet / 5280);
        const ft = Math.round(totalFeet % 5280);

        if (mi > 0) {
            sumDist.innerHTML = `${mi}.${String(Math.round(ft/5280*100)).padStart(2, '0')}`;
            sumDist.innerHTML += `<span class="metric-unit">mi</span>`;
            sumDistFt.textContent = `${(totalFeet/1000).toFixed(1)}k ft`;
        } else {
            sumDist.innerHTML = `${ft}`;
            sumDist.innerHTML += `<span class="metric-unit">ft</span>`;
            sumDistFt.textContent = `${(totalFeet * 0.3048).toFixed(0)} m`;
        }

        // Load visualizations with cache buster
        const cacheBuster = `?t=${Date.now()}`;
        resultMap.src = data.map_url + cacheBuster;
        resultChart.src = data.chart_url + cacheBuster;
        resultDist.src = data.dist_plot_url + cacheBuster;

        // Set Statistics
        statsMean.textContent = data.data_summary.stats.mean;
        statsStd.textContent = data.data_summary.stats.std;

        // Set Download Links
        downloadProfile.href = data.chart_url;
        downloadMap.href = data.map_url;
        downloadDist.href = data.dist_plot_url;
        downloadExcel.href = data.excel_url;

        // Animate value counters
        animateValue(sumTraces, 0, traces, 1000);
        animateValue(statsMean, 0, data.data_summary.stats.mean, 1000, true);
        animateValue(statsStd, 0, data.data_summary.stats.std, 1000, true);
    }

    // Show Results with Animation
    function showResults() {
        resultsSection.classList.remove('hidden');

        // Staggered reveal
        setTimeout(() => {
            summaryCards.classList.remove('hidden');
            summaryCards.style.animation = 'slide-up 0.5s ease-out';
        }, 100);

        setTimeout(() => {
            chartContainer.classList.remove('hidden');
            chartContainer.style.animation = 'slide-up 0.5s ease-out 0.1s both';
        }, 300);

        setTimeout(() => {
            mapContainer.classList.remove('hidden');
            mapContainer.style.animation = 'slide-up 0.5s ease-out 0.2s both';
        }, 500);

        setTimeout(() => {
            distContainer.classList.remove('hidden');
            distContainer.style.animation = 'slide-up 0.5s ease-out 0.3s both';
        }, 600);

        setTimeout(() => {
            exportContainer.classList.remove('hidden');
            exportContainer.style.animation = 'slide-up 0.5s ease-out 0.4s both';
        }, 700);
    }

    // Hide Results
    function hideResults() {
        resultsSection.classList.add('hidden');
        summaryCards.classList.add('hidden');
        chartContainer.classList.add('hidden');
        mapContainer.classList.add('hidden');
        distContainer.classList.add('hidden');
        exportContainer.classList.add('hidden');
    }

    // Animate Numeric Value
    function animateValue(element, start, end, duration, decimals = false) {
        const startTime = performance.now();
        const formatter = new Intl.NumberFormat('en-US', {
            minimumFractionDigits: decimals ? 2 : 0,
            maximumFractionDigits: decimals ? 2 : 0
        });

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Easing function (ease-out)
            const easeOut = 1 - Math.pow(1 - progress, 3);
            const current = Math.floor(start + (end - start) * easeOut);

            element.textContent = formatter.format(current);

            if (progress < 1) {
                requestAnimationFrame(update);
            } else {
                element.textContent = formatter.format(end);
            }
        }

        requestAnimationFrame(update);
    }

    // Latency Simulation
    function startLatencySimulation() {
        setInterval(() => {
            const baseLatency = 12;
            const variance = Math.floor(Math.random() * 8) - 4;
            latencyDisplay.textContent = `${baseLatency + variance}ms`;
        }, 2000);
    }

    // Coordinate Tracking (simulated for visual effect)
    function initCoordinateTracking() {
        const latDisplay = document.getElementById('lat-display');
        const lonDisplay = document.getElementById('lon-display');

        // Only update when results are visible and map is loaded
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.target === mapContainer && !mutation.target.classList.contains('hidden')) {
                    simulateCoordinates();
                }
            });
        });

        observer.observe(mapContainer, { attributes: true, attributeFilter: ['class'] });

        function simulateCoordinates() {
            let lat = 29.7604;
            let lon = -95.3698;

            const interval = setInterval(() => {
                if (mapContainer.classList.contains('hidden')) {
                    clearInterval(interval);
                    return;
                }

                // Simulate minor coordinate drift (as if reading from GPS)
                lat += (Math.random() - 0.5) * 0.0001;
                lon += (Math.random() - 0.5) * 0.0001;

                latDisplay.textContent = lat.toFixed(6);
                lonDisplay.textContent = lon.toFixed(6);
            }, 1000);
        }
    }

    // Keyboard Shortcuts
    document.addEventListener('keydown', (e) => {
        // Ctrl/Cmd + Enter to submit
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            if (!submitBtn.disabled) {
                form.dispatchEvent(new Event('submit'));
            }
        }
    });

    // Console Easter Egg
    console.log('%c GPR ANALYTICS ', 'background: #f59e0b; color: #0a0a0c; font-weight: bold; font-size: 20px; padding: 10px 20px;');
    console.log('%c Subsurface Intelligence Platform v2.4.0 ', 'color: #a1a1aa; font-family: monospace;');
});
