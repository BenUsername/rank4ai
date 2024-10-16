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

    // Add prompts
    mainContent.innerHTML += `
        <h3>Generated Prompts</h3>
        <ol>
            ${data.prompts.map(prompt => `<li>${prompt}</li>`).join('')}
        </ol>
    `;

    // Add results table
    mainContent.innerHTML += `
        <h3>Analysis Results</h3>
        <table>
            <thead>
                <tr>
                    <th>Prompt</th>
                    <th>Answer</th>
                </tr>
            </thead>
            <tbody>
                ${data.table.map(row => `
                    <tr>
                        <td>${row.prompt}</td>
                        <td>${row.answer}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    // Make sure the main content is visible
    mainContent.style.display = 'block';
}

function formatVisibility(visible) {
    return visible.includes('Yes') ? '<span style="color: green;">✓ Yes</span>' : '<span style="color: red;">✗ No</span>';
}

function attachEventListeners() {
    console.log('Attaching event listeners');
    document.querySelectorAll('.expand-btn').forEach(button => {
        button.addEventListener('click', function() {
            const content = this.previousElementSibling;
            content.classList.toggle('expanded');
            this.textContent = content.classList.contains('expanded') ? '-' : '+';
        });
    });
}

function init() {
    console.log('Initializing');
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', afterDOMLoaded);
    } else {
        afterDOMLoaded();
    }
}

function afterDOMLoaded() {
    console.log('DOM fully loaded');
    const analyzeForm = document.getElementById('analyzeForm');
    if (analyzeForm) {
        analyzeForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const domain = document.getElementById('domainInput').value;
            const submitButton = document.querySelector('button[type="submit"]');
            const originalButtonText = submitButton.textContent;
            submitButton.disabled = true;
            submitButton.textContent = 'Analyzing...';

            // Show spinner and progress log
            const spinner = document.getElementById('spinner');
            const progressLog = document.getElementById('progress-log');
            spinner.style.display = 'block';
            progressLog.innerHTML = '';

            // Start progress updates
            let progressStep = 0;
            const progressInterval = setInterval(() => {
                progressStep++;
                switch(progressStep) {
                    case 1:
                        updateProgress('Fetching website content...');
                        break;
                    case 2:
                        updateProgress('Analyzing content...');
                        break;
                    case 3:
                        updateProgress('Generating prompts...');
                        break;
                    case 4:
                        updateProgress('Simulating LLM responses...');
                        break;
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
                    console.log('Received data:', data); // Add this line for debugging
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
        });
    }

    attachEventListeners();
}

function updateProgress(message) {
    const progressLog = document.getElementById('progress-log');
    progressLog.innerHTML += `<p>${message}</p>`;
}

// Call init immediately
init();
