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
    var dummy = document.createElement("input");
    document.body.appendChild(dummy);
    dummy.value = window.location.href;
    dummy.select();
    document.execCommand("copy");
    document.body.removeChild(dummy);
    alert("Link copied to clipboard!");
}

// Function to load and display results
function displayResults(data) {
    const mainContent = document.getElementById('main-content');
    if (!mainContent) {
        console.error('Main content element not found');
        return;
    }
    
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
                    <th>Visibility Score</th>
                </tr>
            </thead>
            <tbody>
                ${data.table.map(row => `
                    <tr>
                        <td>${row.prompt}</td>
                        <td class="truncate">${row.response}</td>
                        <td>${row.visibility_score}</td>
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

    // Add CTA
    mainContent.innerHTML += `
        <div class="cta-container">
            <p class="cta-text">Want to improve your AI search visibility?</p>
            <a href="#" class="cta-button" id="getAdviceButton">Get Personalized Advice</a>
        </div>
    `;

    // Add event listener for the "Get Personalized Advice" button
    document.getElementById('getAdviceButton').addEventListener('click', function(e) {
        e.preventDefault();
        showAdviceModal();
    });
}

function init() {
    console.log('Initializing');
    attachEventListeners();
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
    
    let progress = 0;
    const progressInterval = setInterval(() => {
        progress += 10;
        if (progress <= 100) {
            updateProgress(`Analyzing... ${progress}%`);
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
        alert(`An error occurred: ${error.message}. Please try again.`);
    })
    .finally(() => {
        submitButton.disabled = false;
        submitButton.textContent = originalButtonText;
    });
}

function updateProgress(message) {
    const progressLog = document.getElementById('progress-log');
    progressLog.innerHTML += `<p>${message}</p>`;
}

function showAdviceModal() {
    // Implementation for showing advice modal
    console.log('Showing advice modal');
    // You can implement the modal functionality here
}

// Make sure init() is called when the DOM is loaded
document.addEventListener('DOMContentLoaded', init);
