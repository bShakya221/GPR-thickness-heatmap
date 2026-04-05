import './style.css'

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('upload-form');
    const submitBtn = document.getElementById('submit-btn');
    const btnText = document.getElementById('btn-text');
    const btnSpinner = document.getElementById('btn-spinner');
    const errorMessage = document.getElementById('error-message');
    
    // Result panels
    const summaryCards = document.getElementById('summary-cards');
    const chartContainer = document.getElementById('chart-container');
    const mapContainer = document.getElementById('map-container');
    
    // Visual elements
    const resultMap = document.getElementById('result-map');
    const resultChart = document.getElementById('result-chart');
    const sumTraces = document.getElementById('sum-traces');
    const sumDist = document.getElementById('sum-dist');

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Reset states
        errorMessage.classList.add('hidden');
        errorMessage.textContent = '';
        
        // Hide previous results
        summaryCards.classList.add('hidden');
        chartContainer.classList.add('hidden');
        mapContainer.classList.add('hidden');
        
        // Loading UI
        submitBtn.disabled = true;
        btnText.textContent = 'Processing Payload...';
        btnSpinner.classList.remove('hidden');
        submitBtn.classList.add('opacity-75', 'cursor-not-allowed');

        try {
            const formData = new FormData(form);
            
            // Use relative URL so it functions dynamically in production against the unified backend
            const response = await fetch('/analyze', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || `Server error: ${response.status}`);
            }

            const data = await response.json();

            // Populate summary
            sumTraces.textContent = data.data_summary.traces_parsed.toLocaleString();
            
            // Format distance (feet to miles & feet)
            const totalFeet = data.data_summary.total_distance_ft;
            const mi = Math.floor(totalFeet / 5280);
            const ft = Math.round(totalFeet % 5280);
            sumDist.textContent = mi > 0 ? `${mi} mi ${ft} ft` : `${ft} ft`;
            
            // Populate visuals
            // Add a cache buster parameter to prevent browser caching of identical names on re-uploads
            const cacheBuster = `?t=${new Date().getTime()}`;
            resultMap.src = data.map_url + cacheBuster;
            resultChart.src = data.chart_url + cacheBuster;
            
            // Show panels with staggering
            setTimeout(() => summaryCards.classList.remove('hidden'), 100);
            setTimeout(() => chartContainer.classList.remove('hidden'), 200);
            setTimeout(() => mapContainer.classList.remove('hidden'), 300);

        } catch (error) {
            console.error('Analysis failed:', error);
            errorMessage.textContent = error.message;
            errorMessage.classList.remove('hidden');
        } finally {
            // Restore UI
            submitBtn.disabled = false;
            btnText.textContent = 'Execute Analysis Sequence';
            btnSpinner.classList.add('hidden');
            submitBtn.classList.remove('opacity-75', 'cursor-not-allowed');
        }
    });
});
