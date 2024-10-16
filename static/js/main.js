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
    const resultsSection = document.getElementById('results');
    let html = `<h2>Results for ${data.domain}</h2>`;
    html += `<h3>Website Information</h3>`;
    html += `<p><strong>Title:</strong> ${data.info.title}</p>`;
    html += `<p><strong>Description:</strong> ${data.info.description}</p>`;
    
    html += `<h3>Search Results</h3>`;
    html += `<table>
                <tr>
                    <th>Prompt</th>
                    <th>Answer</th>
                    <th>Visible</th>
                </tr>`;
    
    data.results.forEach(result => {
        html += `<tr>
                    <td>${result.prompt}</td>
                    <td>${result.answer}</td>
                    <td>${result.visible ? 'Yes' : 'No'}</td>
                </tr>`;
    });
    
    html += `</table>`;
    resultsSection.innerHTML = html;
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
    const resultsSection = document.getElementById('results');
    spinner.style.display = 'block';
    resultsSection.innerHTML = '';

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
        spinner.style.display = 'none';
        displayResults(data);
    })
    .catch(error => {
        spinner.style.display = 'none';
        resultsSection.innerHTML = `<p class="error">Error: ${error.message}</p>`;
    })
    .finally(() => {
        submitButton.disabled = false;
        submitButton.textContent = originalButtonText;
    });
}

function showAdviceModal() {
    // Implementation for showing advice modal
    console.log('Showing advice modal');
    // You can implement the modal functionality here
}

// Make sure init() is called when the DOM is loaded
document.addEventListener('DOMContentLoaded', init);
