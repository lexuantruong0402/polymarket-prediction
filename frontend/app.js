document.addEventListener('DOMContentLoaded', () => {
    const marketUrlInput = document.getElementById('market-url');
    const processBtn = document.getElementById('process-btn');
    const btnText = processBtn.querySelector('.btn-text');
    const btnLoader = processBtn.querySelector('.loader-inner');
    const pipelineSection = document.getElementById('pipeline-status');
    const resultsSection = document.getElementById('results');

    let eventSource = null;
    let pipelineComplete = false;

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
        pipelineComplete = false;
        resultsSection.style.display = 'none';
        resultsSection.innerHTML = '';
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
            console.log('SSE message received:', event.data);
            try {
                const payload = JSON.parse(event.data);
                handleUpdate(payload);
            } catch (e) {
                console.error('Failed to parse SSE data:', e);
            }
        };

        eventSource.onerror = (err) => {
            console.warn('SSE connection closed/error:', err);
            eventSource.close();
            // Only reset button if pipeline didn't complete normally
            if (!pipelineComplete) {
                console.error('SSE error before pipeline completed');
                setButtonReady();
            }
        };
    }

    function handleUpdate(payload) {
        const { stage, data } = payload;
        console.log('Handling stage:', stage, data);
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
                if (stage === 'RESEARCH') descText.textContent = `Gathered signals for ${data.signals || 'the'} market`;
                if (stage === 'PREDICT') descText.textContent = `Calibrated ${data.predictions || 'the'} prediction`;
            } else if (data.status === 'aborted') {
                statusText.textContent = 'Aborted';
                statusText.style.color = 'var(--error)';
                descText.textContent = data.reason || 'Pipeline aborted';
            }
        }

        if (stage === 'COMPLETE') {
            console.log('COMPLETE received, rendering results...');
            pipelineComplete = true;
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
        console.log('Rendering results:', summary);
        resultsSection.style.display = 'block';
        resultsSection.innerHTML = ''; // Full container clear

        if (!summary.predictions || summary.predictions.length === 0) {
            console.warn('No predictions in summary');
            resultsSection.innerHTML = '<div class="glass results-card slide-up"><p>No predictions generated.</p></div>';
            return;
        }

        summary.predictions.forEach((pred, index) => {
            const card = document.createElement('div');
            card.className = 'glass results-card slide-up';
            card.style.animationDelay = `${0.2 + (index * 0.1)}s`;

            // Mapping status to CSS class
            const statusClass = pred.status === 'Yes' ? 'status-yes' : 
                              pred.status === 'No' ? 'status-no' : 'status-low';

            card.innerHTML = `
                <div class="results-header">
                    <h2>Market Analysis #${index + 1}</h2>
                    <span class="badge ${statusClass}">${pred.status}</span>
                </div>
                
                <div class="market-question">${pred.question}</div>

                <div class="results-grid">
                    <div class="result-item">
                        <div class="result-label">Model Probability</div>
                        <div class="result-value">${(pred.p_model * 100).toFixed(1)}%</div>
                    </div>
                    <div class="result-item">
                        <div class="result-label">Market Odds (Yes)</div>
                        <div class="result-value">${(pred.p_market * 100).toFixed(1)}%</div>
                    </div>
                    <div class="result-item">
                        <div class="result-label">Edge</div>
                        <div class="result-value" style="color: ${pred.edge > 0 ? 'var(--secondary)' : 'var(--error)'}">
                            ${(pred.edge * 100).toFixed(1)}%
                        </div>
                    </div>
                    <div class="result-item">
                        <div class="result-label">Confidence Score</div>
                        <div class="result-value">${(pred.confidence * 100).toFixed(0)}/100</div>
                    </div>
                    
                    ${pred.reasoning ? `
                    <div class="result-item" style="grid-column: 1 / -1; margin-top: 1rem;">
                        <div class="result-label">LLM Calibration Reasoning</div>
                        <div class="result-value" style="font-size: 1rem; font-weight: 400; margin-top: 0.5rem; opacity: 0.8; line-height: 1.6;">
                            ${pred.reasoning}
                        </div>
                    </div>` : ''}
                </div>

                <div class="research-section" style="margin-top: 2rem;">
                    <h3 style="margin-bottom: 1rem; font-size: 1.1rem; opacity: 0.9;">Research Sources</h3>
                    <div class="research-list">
                        ${renderResearchItems(summary.research[pred.market_id] || [])}
                    </div>
                </div>
            `;
            resultsSection.appendChild(card);
        });
        
        resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    function renderResearchItems(researchData) {
        if (researchData.length === 0) {
            return '<p style="opacity: 0.6; font-size: 0.9rem;">No research articles found for this specific market.</p>';
        }

        return researchData.map(sig => {
            if (!sig.url) return '';
            const sentimentColor = sig.sentiment > 0.1 ? 'var(--success)' : sig.sentiment < -0.1 ? 'var(--error)' : 'white';
            return `
                <div class="research-item" style="padding: 1rem 0; border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                        <div style="flex: 1;">
                            <h4 style="margin: 0; font-size: 1rem;">
                                <a href="${sig.url}" target="_blank" style="text-decoration: none; color: var(--secondary); transition: opacity 0.2s;">
                                    ${sig.narrative}
                                </a>
                            </h4>
                            <p style="margin: 0.3rem 0 0; font-size: 0.8rem; opacity: 0.6;">Source: ${sig.source.toUpperCase()}</p>
                        </div>
                        <div style="margin-left: 1rem; font-weight: 600; font-size: 0.9rem; color: ${sentimentColor}">
                            ${sig.sentiment > 0 ? '+' : ''}${sig.sentiment.toFixed(2)}
                        </div>
                    </div>
                </div>
            `;
        }).join('');
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
        });
    }

    function setButtonReady() {
        processBtn.disabled = false;
        btnText.style.display = 'block';
        btnLoader.style.display = 'none';
    }
});
