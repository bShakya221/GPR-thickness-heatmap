
import './style.css';

// TxDOT GPR Analytics — Main Application Logic
// Developed by Texas Tech University

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

    // Column Selection Elements
    const columnSelectionWrapper = document.getElementById('column-selection-wrapper');
    const columnPreviewGrid = document.getElementById('column-preview-grid');
    const thicknessColumnInput = document.getElementById('thickness_column');

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

    // Parameter Inputs
    const offsetInput = document.getElementById('antenna_offset');
    const offsetSlider = document.getElementById('offset-slider');

    // Latency Display
    const latencyDisplay = document.getElementById('latency');

    // Initialize
    resultsSection.classList.add('hidden');
    hideResults();
    initDragDrop();
    initParamSync();
    startLatencySimulation();
    initCoordinateTracking();

    // File Upload Handling
    kmlInput.addEventListener('change', (e) => handleFileSelect(e, kmlZone, kmlFilename, 'KML'));
    gprInput.addEventListener('change', (e) => handleFileSelect(e, gprZone, gprFilename, 'OUT'));

    // GPR File Special Handling: Get Previews
    gprInput.addEventListener('change', handleGprUpload);

    // Form Submission
    form.addEventListener('submit', handleSubmit);

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

    // GPR Preview Logic
    async function handleGprUpload() {
        const file = gprInput.files[0];
        if (!file) {
            columnSelectionWrapper.classList.add('hidden');
            return;
        }

        try {
            const formData = new FormData();
            formData.append('gpr_file', file);

            const response = await fetch('/preview', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error('Preview failed');

            const data = await response.json();
            renderColumnPreviews(data.columns);
            columnSelectionWrapper.classList.remove('hidden');
        } catch (err) {
            console.error('Column preview error:', err);
        }
    }

    function renderColumnPreviews(columns) {
        columnPreviewGrid.innerHTML = '';
        
        // Convert to array of numbers for logical sorting
        const indices = Object.keys(columns).map(Number).sort((a,b) => a-b);

        indices.forEach(idx => {
            const series = columns[idx];
            const card = document.createElement('div');
            card.className = 'preview-card';
            if (idx === 6) card.classList.add('selected'); // Default column

            card.innerHTML = `
                <span class="preview-label">Value ${idx - 1}</span>
                <svg class="sparkline-svg" viewBox="0 0 100 40" preserveAspectRatio="none">
                    <polyline fill="none" stroke="currentColor" stroke-width="2" points="${generatePoints(series)}"/>
                </svg>
            `;

            card.addEventListener('click', () => {
                document.querySelectorAll('.preview-card').forEach(c => c.classList.remove('selected'));
                card.classList.add('selected');
                thicknessColumnInput.value = idx;
            });

            columnPreviewGrid.appendChild(card);
        });
    }

    function generatePoints(data) {
        if (!data || data.length === 0) return "0,20 100,20";
        const min = Math.min(...data);
        const max = Math.max(...data);
        const range = max - min || 1;
        
        return data.map((val, i) => {
            const x = (i / (data.length - 1)) * 100;
            const y = 35 - ((val - min) / range) * 30; // 5px padding
            return `${x.toFixed(1)},${y.toFixed(1)}`;
        }).join(' ');
    }

    // Drag and Drop Initialization
    function initDragDrop() {
        const zones = [kmlZone, gprZone];
        const inputs = { [kmlZone.id]: kmlInput, [gprZone.id]: gprInput };

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
        btnText.textContent = 'EXECUTING ANALYTICS...';
        btnSpinner.classList.add('active');
        btnProgress.style.width = '0%';

        // Simulate progress
        let progress = 0;
        const progressInterval = setInterval(() => {
            progress += Math.random() * 10;
            if (progress > 95) progress = 95;
            btnProgress.style.width = `${progress}%`;
        }, 250);

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
            }, 600);
        }
    }

    // Populate Results Data
    function populateResults(data) {
        // Traces
        const traces = data.data_summary.traces_parsed;
        sumTraces.textContent = traces.toLocaleString();

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

        // Animate value counters
        animateValue(sumTraces, 0, traces, 1000);
    }

    // Show Results with Animation
    function showResults() {
        resultsSection.classList.remove('hidden');
        resultsSection.scrollIntoView({ behavior: 'smooth' });

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
    }

    // Hide Results
    function hideResults() {
        resultsSection.classList.add('hidden');
        summaryCards.classList.add('hidden');
        chartContainer.classList.add('hidden');
        mapContainer.classList.add('hidden');
    }

    // Animate Numeric Value
    function animateValue(element, start, end, duration) {
        const startTime = performance.now();
        const formatter = new Intl.NumberFormat('en-US');

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

    // Coordinate Tracking
    function initCoordinateTracking() {
        const latDisplay = document.getElementById('lat-display');
        const lonDisplay = document.getElementById('lon-display');

        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.target === resultsSection && !mutation.target.classList.contains('hidden')) {
                    simulateCoordinates();
                }
            });
        });

        observer.observe(resultsSection, { attributes: true, attributeFilter: ['class'] });

        function simulateCoordinates() {
            let lat = 29.7604;
            let lon = -95.3698;

            const interval = setInterval(() => {
                if (resultsSection.classList.contains('hidden')) {
                    clearInterval(interval);
                    return;
                }
                lat += (Math.random() - 0.5) * 0.0001;
                lon += (Math.random() - 0.5) * 0.0001;
                latDisplay.textContent = lat.toFixed(6);
                lonDisplay.textContent = lon.toFixed(6);
            }, 1000);
        }
    }

    // Console Easter Egg
    console.log('%c TxDOT GPR ANALYTICS ', 'background: #0054A4; color: #ffffff; font-weight: bold; font-size: 20px; padding: 10px 20px;');
    console.log('%c Developed by Texas Tech University ', 'color: #D71921; font-family: monospace; font-weight: bold;');
});
;
