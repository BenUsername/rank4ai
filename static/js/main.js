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

function getAdvice(domain, prompt) {
    console.log('getAdvice called for domain:', domain, 'prompt:', prompt);

    // Create modal elements
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'block';

    const modalContent = document.createElement('div');
    modalContent.className = 'modal-content';

    const closeBtn = document.createElement('span');
    closeBtn.className = 'close';
    closeBtn.innerHTML = '&times;';
    closeBtn.onclick = function() {
        document.body.removeChild(modal);
    };

    const adviceContent = document.createElement('div');
    adviceContent.id = 'adviceContent';

    modalContent.appendChild(closeBtn);
    modalContent.appendChild(adviceContent);
    modal.appendChild(modalContent);
    document.body.appendChild(modal);

    // Create and add spinner
    const spinner = document.createElement('div');
    spinner.className = 'advice-spinner';
    adviceContent.appendChild(spinner);

    // Fetch advice
    fetch('/get_advice', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ domain: domain, prompt: prompt })
    })
    .then(response => response.json())
    .then(data => {
        spinner.remove();
        if (data.advice) {
            const formattedAdvice = data.advice
                .replace(/^\d+\.\s*/gm, '')
                .split('\n')
                .filter(item => item.trim() !== '')
                .map(item => `<li>${item}</li>`)
                .join('');
            adviceContent.innerHTML = `
                <h3>Advice for improving visibility of ${domain} for "${prompt}":</h3>
                <ol>${formattedAdvice}</ol>
            `;
        } else {
            adviceContent.innerHTML = '<p>Failed to get advice. Please try again.</p>';
        }
    })
    .catch((error) => {
        console.error('Error:', error);
        adviceContent.innerHTML = '<p class="error">An error occurred while fetching advice. Please try again.</p>';
    });

    // Close modal when clicking outside
    window.onclick = function(event) {
        if (event.target == modal) {
            document.body.removeChild(modal);
        }
    };
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
        ${data.prompts.map((prompt, index) => `<li><a href="#result-${index + 1}">${prompt.split('.', 1)[1].trim().replace(/^"|"$/g, '')}</a></li>`).join('')}
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
                            <div class="content">${row.prompt.split('.', 1)[1].trim().replace(/^"|"$/g, '')}</div>
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
                            ${formatVisibility(row.visible, data.domain, row.prompt, index)}
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

    // Re-attach event listeners after updating the DOM
    attachEventListeners();
}

function formatVisibility(visible, domain, prompt, index) {
    if (visible.includes('Yes')) {
        const rank = visible.match(/\d+/)[0];
        let rankText = '';
        switch (rank) {
            case '1': rankText = 'first! 🥇🎉'; break;
            case '2': rankText = 'second! 🥈🎉'; break;
            case '3': rankText = 'third! 🥉🎉'; break;
            default: rankText = `${rank}th! 🎉`;
        }
        return `<span style="color: green;">✓ Yes</span><br>Congrats, you're ${rankText}`;
    } else {
        const encodedPrompt = encodeURIComponent(prompt);
        return `<span style="color: red;">✗ No</span><br><a href="#" onclick="getAdvice('${domain}', '${encodedPrompt}'); return false;">Get Advice</a>`;
    }
}

function attachEventListeners() {
    console.log('Attaching event listeners');
    document.querySelectorAll('.get-advice-btn').forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const domain = this.getAttribute('data-domain');
            const prompt = decodeURIComponent(this.getAttribute('data-prompt'));
            console.log('Get advice button clicked for domain:', domain, 'and prompt:', prompt);
            getAdvice(domain, prompt);
        });
    });

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
            const domain = document.getElementById('domain').value;
            const submitButton = document.querySelector('button[type="submit"]');
            const originalButtonText = submitButton.textContent;
            submitButton.disabled = true;
            submitButton.textContent = 'Analyzing...';

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
                    alert(data.error);
                } else {
                    displayResults(data);
                }
            })
            .catch(error => {
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

// Call init immediately
init();

function closeModal() {
    const modal = document.getElementById('adviceModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

const closeBtn = document.querySelector('.close');
if (closeBtn) {
    closeBtn.onclick = closeModal;
}

window.onclick = function(event) {
    if (event.target == document.getElementById('adviceModal')) {
        closeModal();
    }
}
