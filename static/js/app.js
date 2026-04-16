document.addEventListener('DOMContentLoaded', () => {
    const chatToggle = document.getElementById('chat-toggle-btn');
    const chatWindow = document.getElementById('chat-window');
    const chatCta = document.getElementById('chat-cta');
    const closeChatBtn = document.getElementById('close-chat-btn');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatMessages = document.getElementById('chat-messages');

    // Toggle Chat Window
    chatToggle.addEventListener('click', () => {
        chatWindow.classList.toggle('hidden');
        if (!chatWindow.classList.contains('hidden')) {
            chatInput.focus();
            if (chatCta) chatCta.style.display = 'none'; // Hide CTA once clicked
        }
    });

    closeChatBtn.addEventListener('click', () => {
        chatWindow.classList.add('hidden');
    });

    let chatHistory = [];

    // Handle Chat Submit
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const message = chatInput.value.trim();
        if (!message) return;

        // Add user message to UI
        addMessage(message, 'user-message');
        chatInput.value = '';

        // Add to history
        chatHistory.push({ role: "user", parts: message });

        // Add typing indicator
        const typingId = 'typing-' + Date.now();
        const typingHtml = '<div class="typing-dots"><span></span><span></span><span></span></div>';
        addMessage(typingHtml, 'ai-message', typingId);

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ 
                    message: message,
                    history: chatHistory.slice(0, -1) // Send previous history
                })
            });

            // Remove typing indicator once connection is made
            const typingElement = document.getElementById(typingId);
            if (typingElement) typingElement.remove();

            const reader = response.body.getReader();
            const decoder = new TextDecoder("utf-8");
            let accumulatedText = "";

            // Create a specific message div to constantly update
            const messageId = 'msg-' + Date.now();
            addMessage("", 'ai-message', messageId);
            const messageElement = document.getElementById(messageId);

            let sseBuffer = "";
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                sseBuffer += decoder.decode(value, { stream: true });
                const lines = sseBuffer.split('\n');
                
                // The last element might be an incomplete line, keep it in the buffer
                sseBuffer = lines.pop();
                
                for (const line of lines) {
                    if (line.trim().startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.substring(6));
                            if (data.text) {
                                accumulatedText += data.text;
                                messageElement.innerHTML = marked.parse(accumulatedText);
                                chatMessages.scrollTop = chatMessages.scrollHeight;
                            }
                        } catch (e) {
                            console.error("Error parsing JSON chunk:", e, line);
                        }
                    }
                }
            }

            // Save AI response to history
            chatHistory.push({ role: "model", parts: accumulatedText });

            // Prune history to last 10 messages (5 user, 5 model) to keep tokens low
            if (chatHistory.length > 10) {
                chatHistory = chatHistory.slice(-10);
            }

        } catch (error) {
            console.error('Error fetching chat:', error);
            const typingElement = document.getElementById(typingId);
            if (typingElement) typingElement.remove();
            
            addMessage("I'm sorry, I couldn't reach your Peer Mentor right now. Try again in a second!", 'ai-message error-message');
            // Remove the failed user message from history if it failed
            chatHistory.pop();
        }
    });

    function addMessage(text, className, id = null) {
        const msgDiv = document.createElement('div');
        msgDiv.className = `chat-message ${className}`;
        if (id) msgDiv.id = id;
        
        // Use innerHTML to allow basic bolding, but be careful of XSS
        // Since we are adding our own API responses or strictly sanitized inputs.
        if (className === 'user-message') {
            msgDiv.textContent = text; // Safe text
        } else {
            msgDiv.innerHTML = text; // Allow basic <strong> from our parsing rules
        }

        chatMessages.appendChild(msgDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Handle Upvotes (with LocalStorage Anti-Spam Tracking)
    document.querySelectorAll('.upvote-btn').forEach(btn => {
        const winId = btn.getAttribute('data-win-id');
        
        // Restore local memory on page load
        if (localStorage.getItem(`upvoted_${winId}`)) {
            btn.style.color = 'var(--primary-color)';
            btn.style.cursor = 'not-allowed';
            btn.classList.add('already-upvoted');
        }

        btn.addEventListener('click', async (e) => {
            // Prevent execution if local storage says already clicked
            if (localStorage.getItem(`upvoted_${winId}`)) {
                return;
            }

            const targetIcon = btn.querySelector('i');
            
            try {
                const response = await fetch(`/upvote/${winId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                const data = await response.json();
                if (data.success) {
                    btn.querySelector('.upvote-count').textContent = data.upvotes;
                    
                    // Simple pop animation logic
                    targetIcon.classList.remove('fa-regular');
                    targetIcon.classList.add('fa-solid');
                    setTimeout(() => {
                        targetIcon.classList.remove('fa-solid');
                        targetIcon.classList.add('fa-regular');
                    }, 300);

                    // Lock out the button permanently for this browser
                    localStorage.setItem(`upvoted_${winId}`, 'true');
                    btn.style.color = 'var(--primary-color)';
                    btn.style.cursor = 'not-allowed';
                }
            } catch (error) {
                console.error('Error upvoting:', error);
            }
        });
    });

    // Handle Category Filtering
    const filterBtns = document.querySelectorAll('.filter-btn');
    const feedCards = document.querySelectorAll('.feed-card');

    filterBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Remove active class from all buttons
            filterBtns.forEach(b => b.classList.remove('active'));
            // Add active class to clicked button
            btn.classList.add('active');

            const filterValue = btn.getAttribute('data-filter');

            feedCards.forEach(card => {
                if (filterValue === 'all') {
                    card.style.display = 'flex';
                } else if (card.getAttribute('data-category') === filterValue) {
                    card.style.display = 'flex';
                } else {
                    card.style.display = 'none';
                }
            });
        });
    });

    // Handle Habit Submission (AJAX)
    const winForm = document.getElementById('win-submit-form');
    const submitBtn = document.getElementById('submit-button');
    const ajaxErrorContainer = document.getElementById('ajax-error-container');
    const feedGrid = document.getElementById('community-feed');

    if (winForm) {
        winForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            
            // Lock UI
            submitBtn.disabled = true;
            const originalBtnHtml = submitBtn.innerHTML;
            submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Sharing...';
            ajaxErrorContainer.innerHTML = ''; // Clear old errors

            const formData = new FormData(winForm);
            
            try {
                const response = await fetch('/submit-win', {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (data.success) {
                    // Prepend new card to the grid
                    const newCard = createCardHtml(data.win);
                    if (feedGrid) {
                        feedGrid.insertAdjacentHTML('afterbegin', newCard);
                        // Trigger a slight "new item" animation if we had one, 
                        // but JS insert is instant.
                    } else {
                        // If feed was empty (empty-state), reload might be needed or just replace the empty state
                        location.reload(); 
                    }
                    
                    // Reset form
                    winForm.reset();
                    
                    // Refresh progress bar and chart
                    if (typeof loadData === 'function') {
                        loadData();
                    }
                } else {
                    // Show error
                    let errorMsg = "An unexpected error occurred.";
                    if (data.error === 'rejected') {
                        errorMsg = "Your post was flagged by the system and could not be submitted.";
                    } else if (data.error === 'ratelimit') {
                        errorMsg = "Your Peer Mentor is currently overwhelmed! Please wait 60 seconds and try again.";
                    } else if (data.error === 'timeout') {
                        errorMsg = "Your Peer Mentor is busy right now. Please try again in a moment.";
                    }

                    ajaxErrorContainer.innerHTML = `
                        <div class="error-banner">
                            <i class="fa-solid fa-triangle-exclamation"></i>
                            <span>${errorMsg}</span>
                        </div>
                    `;
                    
                    // Also clear form on rejection to prevent messy text appending
                    winForm.reset();
                }
            } catch (err) {
                console.error("AJAX Error:", err);
                ajaxErrorContainer.innerHTML = `
                    <div class="error-banner">
                        <i class="fa-solid fa-triangle-exclamation"></i>
                        <span>Network error. Please check your connection.</span>
                    </div>
                `;
            } finally {
                // Unlock UI
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnHtml;
            }
        });
    }

    function createCardHtml(win) {
        const categoryLower = win.category.toLowerCase();
        const categoryClass = categoryLower.replace(' ', '-');
        
        let cheerHtml = '';
        if (win.ai_cheer) {
            cheerHtml = `
                <div class="ai-cheer-box">
                    <i class="fa-solid fa-leaf cheer-icon"></i>
                    <p>${win.ai_cheer}</p>
                </div>
            `;
        }

        return `
            <div class="feed-card" data-category="${categoryLower}">
                <div class="card-header">
                    <span class="category-tag tag-${categoryClass}">${win.category}</span>
                </div>
                <p class="habit-text">${win.habit}</p>
                <div class="habit-meta">
                    <div class="meta-time">
                        <i class="fa-regular fa-clock time-icon"></i>
                        <time>${win.timestamp}</time>
                    </div>
                    <button class="upvote-btn" data-win-id="${win.id}" aria-label="Upvote this win">
                        <i class="fa-regular fa-thumbs-up"></i> <span class="upvote-count">${win.upvotes}</span>
                    </button>
                </div>
                ${cheerHtml}
            </div>
        `;
    }

    // Community Progress Bar Update
    function updateSchoolProgress(total) {
        const progressBar = document.getElementById('goal-progress-bar');
        const countText = document.getElementById('current-total');
        if (!progressBar || !countText) return;

        countText.textContent = total;
        const percentage = Math.min((total / 100) * 100, 100);
        progressBar.style.width = percentage + '%';
        
        // Celebratory color if hit 100
        if (total >= 100) {
            progressBar.style.background = 'linear-gradient(90deg, #D4AF37, #FFD700)';
        }
    }

    // Initialize Chart.js Progress Chart
    let progressChart = null;
    async function loadData() {
        try {
            const res = await fetch('/api/chart-data');
            const data = await res.json();
            
            // Update School Progress
            updateSchoolProgress(data.total_count || 0);

            const chartCanvas = document.getElementById('progressChart');
            if (!chartCanvas) return;

            if (progressChart) {
                progressChart.data.labels = data.labels;
                progressChart.data.datasets[0].data = data.data;
                progressChart.update();
            } else {
                progressChart = new Chart(chartCanvas, {
                    type: 'bar',
                    data: {
                        labels: data.labels,
                        datasets: [{
                            label: "Today's Wins",
                            data: data.data,
                            backgroundColor: '#0A5C36', // Forest Green
                            borderRadius: 6,
                        }]
                    },
                    options: {
                        indexAxis: 'y',
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        },
                        scales: {
                            x: {
                                beginAtZero: true,
                                ticks: { precision: 0, stepSize: 1 }
                            }
                        }
                    }
                });
            }
        } catch (err) {
            console.error("Error loading data:", err);
        }
    }

    // Initial Load
    loadData();

    // Export loadData to global scope so it can be called after submission
    window.refreshDashboardData = loadData;
});
