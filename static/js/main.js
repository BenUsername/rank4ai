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
    
    mainContent.innerHTML = `
        <h1>Results for ${data.domain}</h1>
        
        <h2>Website Information</h2>
        <p><strong>Title:</strong> ${data.info.title}</p>
        <p><strong>Description:</strong> ${data.info.description}</p>
        
        <h2>Relevant Searches</h2>
        <ol>
        ${data.prompts.map((prompt, index) => `<li><a href="#result-${index + 1}">${prompt}</a></li>`).join('')}
        </ol>
        
        <h2>Visibility and Competitors</h2>
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Prompt</th>
                        <th>Answer</th>
                        <th>Top Competitors</th>
                        <th>Visible in LLM?</th>
                    </tr>
                </thead>
                <tbody>
                ${data.table.map((row, index) => `
                    <tr id="result-${index + 1}">
                        <td class="expandable">
                            <div class="content">${row.prompt}</div>
                            <button class="expand-btn" aria-label="Expand">+</button>
                        </td>
                        <td class="expandable">
                            <div class="content">${row.answer}</div>
                            <button class="expand-btn" aria-label="Expand">+</button>
                        </td>
                        <td>
                            ${row.competitors !== 'None mentioned' 
                                ? `<ol>${row.competitors.split(', ').map(comp => `<li>${comp}</li>`).join('')}</ol>`
                                : row.competitors}
                        </td>
                        <td class="visibility-status ${row.visible.includes('Yes') ? 'visible' : 'not-visible'}">
                            ${formatVisibility(row.visible)}
                        </td>
                    </tr>
                `).join('')}
                </tbody>
            </table>
        </div>

        <div class="share-container">
            <h3>Share your results:</h3>
            <button onclick="shareTwitter()" class="share-button twitter">
                <i class="fab fa-twitter"></i> Twitter
            </button>
            <button onclick="shareLinkedIn()" class="share-button linkedin">
                <i class="fab fa-linkedin"></i> LinkedIn
            </button>
            <button onclick="shareFacebook()" class="share-button facebook">
                <i class="fab fa-facebook"></i> Facebook
            </button>
            <button onclick="copyLink()" class="share-button copy-link">
                <i class="fas fa-link"></i> Copy Link
            </button>
        </div>

        ${data.searches_left > 0 
            ? `<div class="cta-container">
                <p class="cta-text">You have ${data.searches_left} free searches left. Want to analyze more domains?</p>
                <a href="/" class="cta-button">Analyze Another Domain</a>
               </div>`
            : `<div class="cta-container">
                <p class="cta-text">You've used all your free searches. Want to analyze more domains and get deeper insights?</p>
                <a href="https://mv71z3xpmnl.typeform.com/to/bmN8bM2y" target="_blank" class="cta-button waiting-list-button">Join Waiting List for Premium Access</a>
               </div>`
        }
    `;

    attachEventListeners();
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
                    displayResults(data);
                }
            })
            .catch(error => {
                clearInterval(progressInterval);
                spinner.style.display = 'none';
                progressLog.innerHTML = '';
                console.error('Error:', error);
                alert('An error occurred. Please try again.');
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
