console.log('main.js loaded');

// Global functions for sharing
function shareTwitter() {
    var text = "I just analyzed my website's visibility in AI search results using LLM Search Performance Tracker! Check it out:";
    var url = window.location.href;
    window.open("https://twitter.com/intent/tweet?text=" + encodeURIComponent(text) + "&url=" + encodeURIComponent(url), "_blank");
}

function shareLinkedIn() {
    var url = window.location.href;
    window.open("https://www.linkedin.com/sharing/share-offsite/?url=" + encodeURIComponent(url), "_blank");
}

function shareFacebook() {
    var url = window.location.href;
    window.open("https://www.facebook.com/sharer/sharer.php?u=" + encodeURIComponent(url), "_blank");
}

function copyLink() {
    var currentUrl = new URL(window.location.href);
    var analyzedDomain = document.getElementById('domainInput').value;
    
    if (analyzedDomain) {
        currentUrl.searchParams.set('domain', analyzedDomain);
        currentUrl.searchParams.set('showResults', 'true');
    }

    var dummy = document.createElement("input");
    document.body.appendChild(dummy);
    dummy.value = currentUrl.toString();
    dummy.select();
    document.execCommand("copy");
    document.body.removeChild(dummy);
    alert("Link copied to clipboard!");
}

// Function to load and display results
function displayResults(data) {
    const mainContent = document.getElementById('main-content');
    const landingContent = document.getElementById('landing-content');
    if (!mainContent) {
        console.error('Main content element not found');
        return;
    }
    
    // Hide landing content and show main content
    landingContent.style.display = 'none';
    mainContent.style.display = 'block';

    // Clear previous content
    mainContent.innerHTML = '';

    // Add domain information with logo
    mainContent.innerHTML += `
        <h2>
            ${data.logo_url ? `<img src="${data.logo_url}" alt="${data.domain} logo" style="vertical-align: middle; margin-right: 10px; max-height: 50px;">` : ''}
            Results for ${data.domain}
        </h2>
    `;

    // Add website information
    mainContent.innerHTML += `
        <h3>Website Information</h3>
        <p><strong>Title:</strong> ${data.info.title}</p>
        <p><strong>Description:</strong> ${data.info.description}</p>
    `;

    // Add table of results
    mainContent.innerHTML += `
        <h3>AI Search Visibility Results</h3>
        <p class="result-note"><i class="fas fa-info-circle"></i> These are usually middle-of-funnel results. They typically bring less traffic than top-of-funnel queries but are much more likely to convert.</p>
        <table class="results-table">
            <thead>
                <tr>
                    <th>Prompt</th>
                    <th>AI Response</th>
                    <th>Competitors visible</th>
                    <th>Is ${data.domain} visible?</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                ${data.table.map((row, index) => `
                    <tr>
                        <td>${row.prompt}</td>
                        <td class="ai-response">
                            <div class="truncate">${formatMarkdown(row.answer)}</div>
                        </td>
                        <td>
                            <ol class="competitors-list">
                                ${row.competitors.split(', ').map((competitor, index) => `
                                    <li>
                                        <span class="competitor-order">${index + 1}.</span>
                                        <img src="${get_logo_dev_logo(competitor)}" alt="${competitor} logo" class="competitor-logo" onerror="this.onerror=null; this.src='https://www.google.com/s2/favicons?domain=${competitor}&sz=32';">
                                        <span class="competitor-domain">${competitor}</span>
                                    </li>
                                `).join('')}
                            </ol>
                        </td>
                        <td class="visibility-result">
                            ${getVisibilityMessage(row.visible)}
                        </td>
                        <td>
                            ${row.visible === 'No' ? `
                                <button onclick="getContentUpdates('${data.domain}', '${row.prompt.replace(/'/g, "\\'")}')" class="content-updates-button">
                                    <i class="fas fa-pencil-alt"></i>
                                </button>
                            ` : ''}
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    // Add sharing buttons
    mainContent.innerHTML += `
        <div class="share-container">
            <h3>Share Your Results</h3>
            <button onclick="shareTwitter()" class="share-button twitter"><i class="fab fa-twitter"></i> Share on Twitter</button>
            <button onclick="shareLinkedIn()" class="share-button linkedin"><i class="fab fa-linkedin"></i> Share on LinkedIn</button>
            <button onclick="shareFacebook()" class="share-button facebook"><i class="fab fa-facebook"></i> Share on Facebook</button>
            <button onclick="copyLink()" class="share-button copy-link"><i class="fas fa-link"></i> Copy Link</button>
        </div>
    `;

    // Update searches left
    const searchesLeftElement = document.getElementById('searches-left');
    if (searchesLeftElement) {
        searchesLeftElement.textContent = data.searches_left;
    }
}

function formatMarkdown(text) {
    // Replace **text** with <strong>text</strong>
    return text.replace(/\*\*(\S(.*?\S)?)\*\*/g, '<strong>$1</strong>');
}

function getContentUpdates(domain, prompt) {
    const modal = document.getElementById('adviceModal');
    const modalContent = document.getElementById('adviceModalContent');
    const spinner = document.getElementById('adviceSpinner');
    const adviceContent = document.getElementById('adviceContent');

    modal.style.display = 'block';
    spinner.style.display = 'block';
    adviceContent.innerHTML = '';

    // Add progress log to the modal
    const progressLog = document.createElement('div');
    progressLog.id = 'advice-progress-log';
    modalContent.insertBefore(progressLog, adviceContent);

    let progressSteps = [
        'Analyzing existing content...',
        'Generating content suggestions...',
        'Compiling advice...',
        'Finalizing recommendations...'
    ];

    let currentStep = 0;
    const progressInterval = setInterval(() => {
        if (currentStep < progressSteps.length) {
            updateAdviceProgress(progressSteps[currentStep]);
            currentStep++;
        } else {
            clearInterval(progressInterval);
        }
    }, 2000);

    fetch('/get_advice', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ domain, prompt })
    })
    .then(response => response.json())
    .then(data => {
        if (data.job_id) {
            pollForResults(data.job_id);
        } else {
            // Handle error
            adviceContent.innerHTML = `<p class="error">${data.error || 'An error occurred'}</p>`;
        }
    })
    .catch(error => {
        adviceContent.innerHTML = `<p class="error">Error: ${error.message}</p>`;
    });
}

function pollForResults(jobId) {
    fetch(`/get_advice_result/${jobId}`)
    .then(response => response.json())
    .then(data => {
        if (data.status === "processing") {
            // If still processing, poll again after a delay
            setTimeout(() => pollForResults(jobId), 2000);
        } else {
            // Results are ready, update the UI
            updateAdviceContent(data);
        }
    })
    .catch(error => {
        adviceContent.innerHTML = `<p class="error">Error: ${error.message}</p>`;
    });
}

function updateAdviceContent(data) {
    // Your existing code to update the UI with the advice content
}

function updateAdviceProgress(message) {
    const progressLog = document.getElementById('advice-progress-log');
    if (progressLog) {
        progressLog.innerHTML = `<p>${message}</p>`;
    }
}

function init() {
    console.log('Initializing');
    attachEventListeners();
    handleUrlParams();
    setupAutocomplete();
}

function attachEventListeners() {
    console.log('Attaching event listeners');
    const form = document.getElementById('analyzeForm');
    if (form) {
        form.addEventListener('submit', handleFormSubmit);
    } else {
        console.error('Form element not found');
    }
}

function handleFormSubmit(e) {
    e.preventDefault();
    const domain = document.getElementById('domainInput').value;
    const submitButton = document.getElementById('analyzeButton');
    const originalButtonText = submitButton.textContent;
    submitButton.disabled = true;
    submitButton.textContent = 'Analyzing...';
    
    const spinner = document.getElementById('spinner');
    const progressLog = document.getElementById('progress-log');
    spinner.style.display = 'block';
    progressLog.innerHTML = '';
    
    // Clear autocomplete suggestions
    clearAutocomplete();

    let progressSteps = [
        'Fetching website content...',
        'Analyzing content...',
        'Generating prompts...',
        'Simulating AI responses...',
        'Compiling results...'
    ];

    let currentStep = 0;
    const progressInterval = setInterval(() => {
        if (currentStep < progressSteps.length) {
            updateProgress(progressSteps[currentStep]);
            currentStep++;
        } else {
            clearInterval(progressInterval);
        }
    }, 2000);

    fetch('/analyze', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `domain=${encodeURIComponent(domain)}`
    })
    .then(response => {
        if (!response.ok) {
            if (response.status === 403) {
                throw new Error('You have reached the maximum number of searches (10). Please try again later.');
            } else if (response.status === 503) {
                throw new Error('The server is currently overloaded. Please try again in a few minutes.');
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        clearInterval(progressInterval);
        spinner.style.display = 'none';
        progressLog.innerHTML = '';
        if (data.error) {
            throw new Error(data.error);
        } else {
            console.log('Received data:', data);
            displayResults(data);
            // Clear any previous error messages
            const errorMessage = document.getElementById('error-message');
            errorMessage.textContent = '';
            errorMessage.style.display = 'none';
        }
    })
    .catch(error => {
        clearInterval(progressInterval);
        spinner.style.display = 'none';
        progressLog.innerHTML = '';
        console.error('Error:', error);
        const errorMessage = document.getElementById('error-message');
        errorMessage.textContent = `An error occurred: ${error.message}`;
        errorMessage.style.display = 'block';
    })
    .finally(() => {
        submitButton.disabled = false;
        submitButton.textContent = originalButtonText;  // Reset button text
    });
}

function updateProgress(message) {
    const progressLog = document.getElementById('progress-log');
    progressLog.innerHTML = `<p>${message}</p>`;
}

function showAdviceModal() {
    // Implementation for showing advice modal
    console.log('Showing advice modal');
    // You can implement the modal functionality here
}

function fetchWithRetry(url, options, retries = 3) {
    return fetch(url, options)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .catch(error => {
            if (retries > 0) {
                return fetchWithRetry(url, options, retries - 1);
            }
            throw error;
        });
}

// Add this function to handle URL parameters when the page loads
function handleUrlParams() {
    const urlParams = new URLSearchParams(window.location.search);
    const domain = urlParams.get('domain');
    const showResults = urlParams.get('showResults');

    if (domain && showResults === 'true') {
        document.getElementById('domainInput').value = domain;
        document.getElementById('analyzeForm').dispatchEvent(new Event('submit'));
    }
}

// Make sure init() is called when the DOM is loaded
document.addEventListener('DOMContentLoaded', init);

// Add this at the end of your file
document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('adviceModal');
    const closeBtn = document.getElementsByClassName('close')[0];

    closeBtn.onclick = function() {
        modal.style.display = 'none';
    }

    window.onclick = function(event) {
        if (event.target == modal) {
            modal.style.display = 'none';
        }
    }
});

// Add this function at the end of the file
function setupAutocomplete() {
    const input = document.getElementById('domainInput');
    const resultsContainer = document.getElementById('autocompleteResults');
    const form = document.getElementById('analyzeForm');
    let debounceTimer;
    let currentFocus = -1;

    input.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            const query = this.value;
            if (query.length > 1) {
                fetch(`/autocomplete/${encodeURIComponent(query)}`)
                    .then(response => response.json())
                    .then(data => {
                        console.log("Autocomplete data:", data);
                        resultsContainer.innerHTML = '';
                        if (data.length === 0) {
                            resultsContainer.style.display = 'none';
                        } else {
                            resultsContainer.style.display = 'block';
                            data.forEach((suggestion, index) => {
                                const li = document.createElement('li');
                                li.innerHTML = `
                                    ${suggestion.logo_url ? `<img src="${suggestion.logo_url}" alt="${suggestion.domain} logo" 
                                         style="width: 20px; height: 20px; vertical-align: middle; margin-right: 10px;">` : ''}
                                    ${suggestion.domain}
                                `;
                                li.setAttribute('data-index', index);
                                li.addEventListener('click', () => {
                                    input.value = suggestion.domain;
                                    resultsContainer.innerHTML = '';
                                    resultsContainer.style.display = 'none';
                                });
                                resultsContainer.appendChild(li);
                            });
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        resultsContainer.style.display = 'none';
                    });
            } else {
                resultsContainer.innerHTML = '';
                resultsContainer.style.display = 'none';
            }
        }, 300);
    });

    form.addEventListener('submit', clearAutocomplete);

    input.addEventListener('keydown', function(e) {
        const items = resultsContainer.getElementsByTagName('li');
        if (e.keyCode === 40) { // Arrow down
            e.preventDefault();
            currentFocus++;
            addActive(items);
        } else if (e.keyCode === 38) { // Arrow up
            e.preventDefault();
            currentFocus--;
            addActive(items);
        } else if (e.keyCode === 13) { // Enter
            e.preventDefault();
            if (currentFocus > -1 && items.length > 0) {
                items[currentFocus].click();
            }
            clearAutocomplete();
            form.dispatchEvent(new Event('submit'));
        }
    });

    function addActive(items) {
        if (!items) return false;
        removeActive(items);
        if (currentFocus >= items.length) currentFocus = 0;
        if (currentFocus < 0) currentFocus = (items.length - 1);
        items[currentFocus].classList.add('autocomplete-active');
        input.value = items[currentFocus].textContent.trim();
    }

    function removeActive(items) {
        for (let i = 0; i < items.length; i++) {
            items[i].classList.remove('autocomplete-active');
        }
    }

    // Hide results when clicking outside
    document.addEventListener('click', function(e) {
        if (e.target !== input && e.target !== resultsContainer) {
            resultsContainer.innerHTML = '';
            currentFocus = -1;
        }
    });

    // Modify the click event listener for autocomplete items
    resultsContainer.addEventListener('click', function(e) {
        if (e.target && e.target.nodeName === 'LI') {
            input.value = e.target.textContent.trim();
            clearAutocomplete();
            form.dispatchEvent(new Event('submit'));
        }
    });
}

function get_logo_dev_logo(domain) {
    const public_key = "pk_Iiu041TAThCqnelMWeRtDQ";
    const encoded_domain = encodeURIComponent(domain);
    return `https://img.logo.dev/${encoded_domain}?token=${public_key}&size=200&format=png`;
}

function getVisibilityMessage(visible) {
    if (visible === 'No') {
        return 'No';
    } else if (visible === 'Yes') {
        return 'Yes';
    } else {
        const match = visible.match(/\d+/);
        if (match) {
            const rank = parseInt(match[0]);
            if (rank === 1) {
                return '🎉 Congratulations! You\'re first!';
            } else if (rank === 2) {
                return '🥈 Great job! You\'re second!';
            } else if (rank === 3) {
                return '🥉 Nice! You\'re third!';
            } else {
                return `✅ You're ${rank}th`;
            }
        } else {
            return visible; // Return the original value if no number is found
        }
    }
}

// Add this function at the global scope
function clearAutocomplete() {
    const resultsContainer = document.getElementById('autocompleteResults');
    if (resultsContainer) {
        resultsContainer.innerHTML = '';
        resultsContainer.style.display = 'none';
    }
}
