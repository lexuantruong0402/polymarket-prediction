document.addEventListener('DOMContentLoaded', () => {
    const marketUrlInput = document.getElementById('market-url');
    const processBtn = document.getElementById('process-btn');
    const btnText = processBtn.querySelector('.btn-text');
    const btnLoader = processBtn.querySelector('.loader-inner');
    const pipelineSection = document.getElementById('pipeline-status');
    const resultsSection = document.getElementById('results');
    const resultsContent = document.getElementById('results-content');

    let eventSource = null;

    processBtn.addEventListener('click', () => {
        const url = marketUrlInput.value.trim();
        if (!url) {
            alert('Please enter a valid Polymarket URL');
            return;
        }

        startProcessing(url);
    });

    function startProcessing(url) {
        // Reset UI
        resultsSection.style.display = 'none';
        pipelineSection.style.display = 'block';
        resetTimeline();
        
        // Show loading state
        processBtn.disabled = true;
        btnText.style.display = 'none';
        btnLoader.style.display = 'block';

        if (eventSource) {
            eventSource.close();
        }

        const encodedUrl = encodeURIComponent(url);
        eventSource = new EventSource(`http://localhost:8000/process?url=${encodedUrl}`);

        eventSource.onmessage = (event) => {
            const payload = JSON.parse(event.data);
            handleUpdate(payload);
        };

        eventSource.onerror = (err) => {
            console.error('SSE Error:', err);
            eventSource.close();
            setButtonReady();
        };
    }

    function handleUpdate(payload) {
        const { stage, data } = payload;
        const stepElement = document.getElementById(`step-${stage}`);

        if (stepElement) {
            // Activate current step
            document.querySelectorAll('.timeline-step').forEach(s => s.classList.remove('active'));
            stepElement.classList.add('active');

            const statusText = stepElement.querySelector('.step-status');
            const descText = stepElement.querySelector('.step-info p');

            if (data.status === 'started') {
                statusText.textContent = 'Processing...';
            } else if (data.status === 'complete') {
                stepElement.classList.add('completed');
                statusText.textContent = '✓';
                
                // Update description based on data
                if (stage === 'SCAN') descText.textContent = `Found ${data.count} sub-markets`;
                if (stage === 'RESEARCH') descText.textContent = `Gathered ${data.signals} signals`;
                if (stage === 'PREDICT') descText.textContent = `Generated ${data.predictions} predictions`;
                if (stage === 'RISK') descText.textContent = `Approved: ${data.approved} / Rejected: ${data.rejected}`;
                if (stage === 'EXECUTE') descText.textContent = `Simulated ${data.trades} trades`;
                if (stage === 'COMPOUND') descText.textContent = `Synthesized ${data.insights} insights`;
            } else if (data.status === 'aborted') {
                statusText.textContent = 'Aborted';
                statusText.style.color = 'var(--error)';
                descText.textContent = data.reason || 'Pipeline aborted';
            }
        }

        if (stage === 'COMPLETE') {
            renderResults(data);
            eventSource.close();
            setButtonReady();
            document.querySelectorAll('.timeline-step').forEach(s => s.classList.remove('active'));
        }

        if (stage === 'ERROR') {
            alert(`Error: ${data.message}`);
            eventSource.close();
            setButtonReady();
        }
    }

    function renderResults(summary) {
        resultsSection.style.display = 'block';
        resultsContent.innerHTML = '';

        const items = [
            { label: 'Markets Scanned', value: summary.markets_scanned },
            { label: 'Predictions', value: summary.predictions },
            { label: 'Approved', value: summary.approved },
            { label: 'Trades Simulated', value: summary.trades_executed },
            { label: 'Insights', value: summary.insights_generated }
        ];

        items.forEach(item => {
            const el = document.createElement('div');
            el.className = 'result-item slide-up';
            el.innerHTML = `
                <div class="result-label">${item.label}</div>
                <div class="result-value">${item.value}</div>
            `;
            resultsContent.appendChild(el);
        });
        
        // Scroll to results
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    function resetTimeline() {
        document.querySelectorAll('.timeline-step').forEach(step => {
            step.classList.remove('active', 'completed');
            step.querySelector('.step-status').textContent = '';
            
            // Restore default text
            const stage = step.id.replace('step-', '');
            const p = step.querySelector('.step-info p');
            if (stage === 'SCAN') p.textContent = 'Fetching market data...';
            if (stage === 'RESEARCH') p.textContent = 'Gathering sentiment & news...';
            if (stage === 'PREDICT') p.textContent = 'Running ML calibration...';
            if (stage === 'RISK') p.textContent = 'Evaluating exposure & Kelly...';
            if (stage === 'EXECUTE') p.textContent = 'Simulating trade placement...';
            if (stage === 'COMPOUND') p.textContent = 'Synthesized insights...';
        });
    }

    function setButtonReady() {
        processBtn.disabled = false;
        btnText.style.display = 'block';
        btnLoader.style.display = 'none';
    }
});
