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

    // Add domain information
    mainContent.innerHTML += `<h2>Results for ${data.domain}</h2>`;

    // Add website information
    mainContent.innerHTML += `
        <h3>Website Information</h3>
        <p><strong>Title:</strong> ${data.info.title}</p>
        <p><strong>Description:</strong> ${data.info.description}</p>
    `;

    // Add table of results
    mainContent.innerHTML += `
        <h3>AI Search Visibility Results</h3>
        <table>
            <thead>
                <tr>
                    <th>Prompt</th>
                    <th>AI Response</th>
                    <th>Competitors</th>
                    <th>Are You Visible?</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                ${data.table.map((row, index) => `
                    <tr>
                        <td>${row.prompt}</td>
                        <td class="truncate">${row.answer}</td>
                        <td>${row.competitors}</td>
                        <td>${row.visible}</td>
                        <td>${row.visible === 'No' ? `<button onclick="getAdvice('${data.domain}', '${row.prompt}', ${index})" class="advice-button">Get Advice</button>` : ''}</td>
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

function getAdvice(domain, prompt, rowIndex) {
    const modal = document.getElementById('adviceModal');
    const modalContent = document.getElementById('adviceModalContent');
    const spinner = document.getElementById('adviceSpinner');
    const adviceContent = document.getElementById('adviceContent');

    modal.style.display = 'block';
    spinner.style.display = 'block';
    adviceContent.innerHTML = '';

    fetch('/get_advice', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ domain, prompt })
    })
    .then(response => response.json())
    .then(data => {
        spinner.style.display = 'none';
        const formattedAdvice = data.advice.replace(/(\d+\.)/g, '<br><br>$1').replace(/Example:/g, '<br>Example:');
        adviceContent.innerHTML = `<h3>Advice for improving visibility:</h3>${formattedAdvice}`;
    })
    .catch(error => {
        spinner.style.display = 'none';
        adviceContent.innerHTML = `<p class="error">Error: ${error.message}</p>`;
    });
}

function init() {
    console.log('Initializing');
    attachEventListeners();
    handleUrlParams();
}

function attachEventListeners() {
    console.log('Attaching event listeners');
    const form = document.getElementById('analyzeForm');
    if (form) {
        form.addEventListener('submit', handleFormSubmit);
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
            if (response.status === 503) {
                throw new Error('The server is currently unavailable. Please try again later.');
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
        }
    })
    .catch(error => {
        clearInterval(progressInterval);
        spinner.style.display = 'none';
        progressLog.innerHTML = '';
        console.error('Error:', error);
        const errorMessage = document.getElementById('error-message');
        errorMessage.textContent = `An error occurred: ${error.message}. Please try again later.`;
        errorMessage.style.display = 'block';
    })
    .finally(() => {
        submitButton.disabled = false;
        submitButton.textContent = originalButtonText;
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
