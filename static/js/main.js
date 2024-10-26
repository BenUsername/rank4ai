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
    const errorMessage = document.getElementById('error-message');
    const spinner = document.getElementById('spinner');
    const progressLog = document.getElementById('progress-log');  // Define progressLog here
    
    // Hide specific nav items when showing results
    document.getElementById('how-it-works-link').style.display = 'none';
    document.getElementById('success-stories-link').style.display = 'none';
    document.getElementById('faq-link').style.display = 'none';
    
    if (!mainContent) {
        console.error('Main content element not found');
        return;
    }
    
    // Hide error message if it was previously shown
    errorMessage.style.display = 'none';
    
    // Hide landing content and show main content
    landingContent.style.display = 'none';
    mainContent.style.display = 'block';

    // Stop the spinner and reset the button
    if (spinner) spinner.style.display = 'none';
    if (progressLog) progressLog.innerHTML = '';
    
    const analyzeButton = document.getElementById('analyzeButton');
    if (analyzeButton) {
        analyzeButton.disabled = false;
        analyzeButton.textContent = 'Analyze';
    }

    // Clear previous content
    mainContent.innerHTML = '';

    const score = Math.round(data.score);
    const scoreColor = getScoreColor(score);
    const circumference = 2 * Math.PI * 90; // Circumference of the circle
    const dashArray = (score / 100) * circumference; // Adjust fill based on score

    mainContent.innerHTML += `
        <div class="results-header">
            <h2>
                ${data.logo_url ? `<img src="${data.logo_url}" alt="${data.domain} logo" style="vertical-align: middle; margin-right: 10px; max-height: 50px;">` : ''}
                Results for ${data.domain}
            </h2>
            <div class="score-container">
                <div class="score-circle" style="background-color: ${scoreColor}11;">
                    <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
                        <circle cx="100" cy="100" r="90" fill="none" stroke="${scoreColor}33" stroke-width="12"/>
                        <circle cx="100" cy="100" r="90" fill="none" stroke="${scoreColor}" stroke-width="12"
                                stroke-dasharray="${circumference}" stroke-dashoffset="${circumference - dashArray}"
                                transform="rotate(-90 100 100)"/>
                    </svg>
                    <span class="score" style="color: ${scoreColor};">${score}</span>
                </div>
                <p>LLM Visibility Score</p>
                <div class="score-legend">
                    <span class="legend-item poor">0-49</span>
                    <span class="legend-item average">50-89</span>
                    <span class="legend-item good">90-100</span>
                </div>
            </div>
        </div>
        <div class="scroll-prompt">
            <p>See whether you are visible in LLM searches, whether your competitors are, and how to improve below</p>
            <i class="fas fa-chevron-down"></i>
        </div>
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
        <p class="result-note"><i class="fas fa-info-circle"></i> A key difference between searching with LLM and Google is that LLM queries are usually longer—about 10 words, while Google queries are often just 2-3 words. Besides users often interact with the LLM a few times refining their queries. This means LLM searches have clearer goals and tend to lead to better conversions, even if they bring in less traffic. We have simulated these behaviours in our analysis. In the table below, the further down the more likely to convert and the smaller the volume. Click our Action recommendation below for tips at each level.</p>
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
                            <div class="response-content">
                                <p>${formatMarkdown(row.answer)}</p>
                            </div>
                            <button class="read-more-btn">Read More</button>
                        </td>
                        <td>
                            <ol class="competitors-list">
                                ${row.competitors ? (Array.isArray(row.competitors) ? 
                                    row.competitors : row.competitors.split(', ')).map((competitor, index) => `
                                    <li>
                                        <span class="competitor-order">${index + 1}.</span>
                                        <img src="${get_logo_dev_logo(competitor)}" alt="${competitor} logo" class="competitor-logo" onerror="this.onerror=null; this.src='https://www.google.com/s2/favicons?domain=${competitor}&sz=32';">
                                        <span class="competitor-domain" title="${competitor}">${competitor}</span>
                                    </li>
                                `).join('') : ''}
                            </ol>
                        </td>
                        <td class="visibility-result">
                            ${getVisibilityMessage(row.visible)}
                        </td>
                        <td>
                            ${row.visible === 'No' ? `
                                <button class="content-updates-button" data-domain="${data.domain}" data-prompt="${row.prompt}">
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

    // Add event listeners for "Read More" buttons
    const readMoreButtons = document.querySelectorAll('.read-more-btn');
    readMoreButtons.forEach(button => {
        button.addEventListener('click', function() {
            const responseContent = this.previousElementSibling;
            if (responseContent.style.maxHeight) {
                responseContent.style.maxHeight = null;
                this.textContent = 'Read More';
            } else {
                responseContent.style.maxHeight = responseContent.scrollHeight + "px";
                this.textContent = 'Read Less';
            }
        });
    });

    // Add event listeners for content update buttons
    const contentUpdateButtons = document.querySelectorAll('.content-updates-button');
    contentUpdateButtons.forEach(button => {
        button.addEventListener('click', function() {
            const domain = this.getAttribute('data-domain');
            const prompt = this.getAttribute('data-prompt');
            getContentUpdates(domain, prompt);
        });
    });
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
            clearInterval(progressInterval);
            spinner.style.display = 'none';
            adviceContent.innerHTML = `<p class="error">${data.error || 'An error occurred'}</p>`;
        }
    })
    .catch(error => {
        clearInterval(progressInterval);
        spinner.style.display = 'none';
        adviceContent.innerHTML = `<p class="error">Error: ${error.message}</p>`;
    });
}

function pollForResults(jobId) {
    fetch(`/get_advice_result/${jobId}`)
    .then(response => response.json())
    .then(data => {
        if (data.status === "processing") {
            setTimeout(() => pollForResults(jobId), 5000);
        } else if (data.error) {
            const adviceContent = document.getElementById('adviceContent');
            adviceContent.innerHTML = `<p class="error">Error: ${data.error}</p>`;
            hideSpinnerAndProgressLog();
        } else {
            updateAdviceContent(data);
            hideSpinnerAndProgressLog();
        }
    })
    .catch(error => {
        const adviceContent = document.getElementById('adviceContent');
        adviceContent.innerHTML = `<p class="error">Error: ${error.message}</p>`;
        hideSpinnerAndProgressLog();
    });
}

function hideSpinnerAndProgressLog() {
    const spinner = document.getElementById('adviceSpinner');
    const progressLog = document.getElementById('advice-progress-log');
    if (spinner) spinner.style.display = 'none';
    if (progressLog) progressLog.style.display = 'none';
}

function updateAdviceContent(data) {
    const adviceContent = document.getElementById('adviceContent');
    let contentHtml = '<h3>Recommendations to Improve LLM Visibility:</h3>';

    if (data.recommendations && data.recommendations.length > 0) {
        contentHtml += '<div class="recommendations-container">';
        data.recommendations.forEach((rec, index) => {
            const typeIcon = {
                'content_update': 'fa-pencil-alt',
                'new_content': 'fa-plus-circle',
                'technical': 'fa-cogs'
            }[rec.type] || 'fa-lightbulb';

            const typeLabel = {
                'content_update': 'Content Update',
                'new_content': 'New Content',
                'technical': 'Technical Optimization'
            }[rec.type] || 'General Recommendation';

            const impactClass = rec.score_impact <= 5 ? 'low-impact' : 
                              rec.score_impact <= 10 ? 'medium-impact' : 
                              'high-impact';

            contentHtml += `
                <div class="recommendation-card">
                    <div class="recommendation-header">
                        <i class="fas ${typeIcon}"></i>
                        <span class="recommendation-type">${typeLabel}</span>
                        <span class="score-impact ${impactClass}">
                            <i class="fas fa-chart-line"></i>
                            +${rec.score_impact} points
                        </span>
                    </div>
                    <h4>${rec.title}</h4>
                    <p class="recommendation-description">${rec.description}</p>
                    <div class="implementation-steps">
                        <h5>Implementation Steps:</h5>
                        <p>${rec.implementation}</p>
                    </div>
                </div>
            `;
        });
        contentHtml += '</div>';
    } else {
        contentHtml += '<p>No recommendations available at this time.</p>';
    }

    adviceContent.innerHTML = contentHtml;
}

function updateAdviceProgress(message) {
    const progressLog = document.getElementById('advice-progress-log');
    if (progressLog) {
        const now = new Date().toLocaleTimeString();
        progressLog.innerHTML += `<p>${now}: ${message}</p>`;
    }
}

// Ensure init() is only called once
let initialized = false;
function init() {
    if (initialized) return;
    initialized = true;
    
    console.log('Initializing');
    attachEventListeners();
    handleUrlParams();
    setupAutocomplete();
    initializeDropdown();
}

// Call init() only once when the DOM is loaded
document.addEventListener('DOMContentLoaded', init, { once: true });

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
    const submitButton = document.getElementById('analyzeButton');
    if (submitButton.disabled) {
        return; // Prevent multiple submissions
    }
    
    const domain = document.getElementById('domainInput').value;
    submitButton.disabled = true;
    submitButton.textContent = 'Analyzing...';
    
    const spinner = document.getElementById('spinner');
    const progressLog = document.getElementById('progress-log');
    spinner.style.display = 'block';
    progressLog.innerHTML = '';
    
    clearAutocomplete();

    fetch('/analyze', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: `domain=${encodeURIComponent(domain)}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            throw new Error(data.error);
        }
        displayResults(data);
    })
    .catch(error => {
        console.error('Error:', error);
        document.getElementById('error-message').textContent = error.message;
        document.getElementById('error-message').style.display = 'block';
        resetProgressIndicators();
    });
}

function resetProgressIndicators() {
    const spinner = document.getElementById('spinner');
    const progressLog = document.getElementById('progress-log');
    const submitButton = document.getElementById('analyzeButton');

    spinner.style.display = 'none';
    progressLog.innerHTML = ''; // Clear progress log
    submitButton.disabled = false;
    submitButton.textContent = 'Analyze';
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

// Add this function at the end of your file
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

function getScoreColor(score) {
    if (score < 50) return '#FF4136'; // Red
    if (score < 90) return '#FF851B'; // Orange
    return '#2ECC40'; // Green
}

document.addEventListener('DOMContentLoaded', function() {
    const showMoreButton = document.getElementById('showMoreBlogs');
    const hiddenItems = document.querySelectorAll('.hidden-blog-item');

    if (showMoreButton) {
        showMoreButton.addEventListener('click', function() {
            hiddenItems.forEach(item => {
                if (item.style.display === 'none' || item.style.display === '') {
                    item.style.display = 'block';
                } else {
                    item.style.display = 'none';
                }
            });
            showMoreButton.textContent = showMoreButton.textContent === 'Show More' ? 'Show Less' : 'Show More';
        });
    }
});

// Add this function to your existing JavaScript
function initializeDropdown() {
    const dropdownBtn = document.querySelector('.dropbtn');
    const dropdownContent = document.querySelector('.dropdown-content');

    if (dropdownBtn && dropdownContent) {
        dropdownBtn.addEventListener('click', function(e) {
            e.preventDefault();
            dropdownContent.style.display = dropdownContent.style.display === 'block' ? 'none' : 'block';
        });

        // Close the dropdown if the user clicks outside of it
        window.addEventListener('click', function(e) {
            if (!e.target.matches('.dropbtn')) {
                dropdownContent.style.display = 'none';
            }
        });
    }
}

