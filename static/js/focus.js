// ========= FOCUS MODE =========
document.addEventListener('DOMContentLoaded', () => {
    const overlay = document.getElementById('focus-overlay');
    const focusBtn = document.getElementById('focus-mode-btn');
    const exitBtn = document.getElementById('focus-exit');
    const startBtn = document.getElementById('focus-start');
    const pauseBtn = document.getElementById('focus-pause');
    const resetBtn = document.getElementById('focus-reset');
    const minutesDisplay = document.getElementById('focus-minutes');
    const secondsDisplay = document.getElementById('focus-seconds');
    const focusLabel = document.getElementById('focus-label');
    const sessionCountEl = document.getElementById('session-count');
    const quoteEl = document.getElementById('focus-quote');
    const modeChips = document.querySelectorAll('.mode-chip');

    if (!overlay || !focusBtn) return;

    let timerInterval = null;
    let totalSeconds = 25 * 60;
    let remainingSeconds = totalSeconds;
    let isRunning = false;
    let currentMode = 'focus';
    let sessionCount = parseInt(localStorage.getItem('focus_sessions_today') || '0');

    // Reset session count if it's a new day
    const lastSessionDate = localStorage.getItem('focus_session_date');
    const today = new Date().toDateString();
    if (lastSessionDate !== today) {
        sessionCount = 0;
        localStorage.setItem('focus_sessions_today', '0');
        localStorage.setItem('focus_session_date', today);
    }
    if (sessionCountEl) sessionCountEl.textContent = sessionCount;

    const quotes = [
        '"The secret of getting ahead is getting started." — Mark Twain',
        '"Focus on being productive instead of busy." — Tim Ferriss',
        '"It does not matter how slowly you go as long as you do not stop." — Confucius',
        '"Small daily improvements are the key to staggering long-term results."',
        '"Your future is created by what you do today, not tomorrow."',
        '"The only way to do great work is to love what you do." — Steve Jobs',
        '"Don\'t count the days, make the days count." — Muhammad Ali',
        '"You don\'t have to be great to start, but you have to start to be great." — Zig Ziglar',
        '"Discipline is the bridge between goals and accomplishment." — Jim Rohn',
        '"A river cuts through rock not because of its power, but because of its persistence."',
    ];

    function randomQuote() {
        if (quoteEl) {
            quoteEl.textContent = quotes[Math.floor(Math.random() * quotes.length)];
        }
    }

    // Open Focus Mode
    focusBtn.addEventListener('click', () => {
        overlay.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        randomQuote();
    });

    // Exit Focus Mode
    exitBtn.addEventListener('click', () => {
        overlay.classList.add('hidden');
        document.body.style.overflow = '';
        stopTimer();
    });

    // Escape key exits
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !overlay.classList.contains('hidden')) {
            overlay.classList.add('hidden');
            document.body.style.overflow = '';
            stopTimer();
        }
    });

    // Mode chips
    modeChips.forEach(chip => {
        chip.addEventListener('click', () => {
            if (isRunning) {
                // If running, stop and reset to switch modes
                stopTimer();
            }
            modeChips.forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            
            const minutes = parseInt(chip.getAttribute('data-minutes'));
            currentMode = chip.getAttribute('data-mode');
            totalSeconds = minutes * 60;
            remainingSeconds = totalSeconds;
            updateDisplay();

            if (currentMode === 'focus') {
                focusLabel.textContent = 'Ready to focus?';
            } else if (currentMode === 'break') {
                focusLabel.textContent = 'Time for a quick break!';
            } else {
                focusLabel.textContent = 'Take a longer break. You earned it.';
            }
        });
    });

    // Start
    startBtn.addEventListener('click', () => {
        if (isRunning) return;
        isRunning = true;
        startBtn.disabled = true;
        pauseBtn.disabled = false;
        resetBtn.disabled = false;
        
        if (currentMode === 'focus') {
            focusLabel.textContent = 'Stay focused. You got this. 💪';
            overlay.classList.add('focusing');
        } else {
            focusLabel.textContent = 'Relax and recharge...';
            overlay.classList.remove('focusing');
        }

        timerInterval = setInterval(() => {
            remainingSeconds--;
            updateDisplay();

            if (remainingSeconds <= 0) {
                clearInterval(timerInterval);
                isRunning = false;
                timerComplete();
            }
        }, 1000);
    });

    // Pause
    pauseBtn.addEventListener('click', () => {
        if (!isRunning) return;
        clearInterval(timerInterval);
        isRunning = false;
        pauseBtn.disabled = true;
        startBtn.disabled = false;
        startBtn.querySelector('i').className = 'fa-solid fa-play';
        startBtn.querySelector('.btn-text').textContent = 'Resume';
        focusLabel.textContent = 'Paused. Take a breath.';
    });

    // Reset
    resetBtn.addEventListener('click', () => {
        stopTimer();
    });

    function stopTimer() {
        clearInterval(timerInterval);
        isRunning = false;
        remainingSeconds = totalSeconds;
        updateDisplay();
        pauseBtn.disabled = true;
        resetBtn.disabled = true;
        startBtn.disabled = false;
        startBtn.querySelector('i').className = 'fa-solid fa-play';
        startBtn.querySelector('.btn-text').textContent = 'Start';
        overlay.classList.remove('focusing');
        
        if (currentMode === 'focus') {
            focusLabel.textContent = 'Ready to focus?';
        } else {
            focusLabel.textContent = 'Ready for a break?';
        }
    }

    function updateDisplay() {
        const mins = Math.floor(remainingSeconds / 60);
        const secs = remainingSeconds % 60;
        minutesDisplay.textContent = mins.toString().padStart(2, '0');
        secondsDisplay.textContent = secs.toString().padStart(2, '0');
    }

    function timerComplete() {
        pauseBtn.disabled = true;
        resetBtn.disabled = true;
        startBtn.disabled = false;
        startBtn.querySelector('i').className = 'fa-solid fa-play';
        startBtn.querySelector('.btn-text').textContent = 'Start';
        overlay.classList.remove('focusing');

        if (currentMode === 'focus') {
            // Focus session complete!
            sessionCount++;
            localStorage.setItem('focus_sessions_today', sessionCount.toString());
            localStorage.setItem('focus_session_date', new Date().toDateString());
            if (sessionCountEl) sessionCountEl.textContent = sessionCount;

            focusLabel.textContent = '🎉 Session complete! Amazing work!';

            // Confetti!
            if (typeof confetti !== 'undefined') {
                confetti({
                    particleCount: 200,
                    spread: 90,
                    origin: { y: 0.5 },
                    colors: ['#0A5C36', '#10B981', '#8B5CF6', '#FCD34D'],
                    zIndex: 100001
                });
            }

            // Auto-post the focus session to the feed
            autoPostFocusSession();

            // Suggest break
            setTimeout(() => {
                focusLabel.textContent = 'Nice! Switch to a break when you\'re ready.';
            }, 3000);
        } else {
            // Break complete
            focusLabel.textContent = '⏰ Break\'s over! Ready for another round?';
        }

        // Reset for next round
        remainingSeconds = totalSeconds;
        updateDisplay();
    }

    async function autoPostFocusSession() {
        try {
            const formData = new FormData();
            formData.append('habit', `Completed a 25-minute Focus Session 🎯`);
            formData.append('category', 'Mindfulness');

            const response = await fetch('/submit-win', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            if (data.success) {
                console.log('Focus session auto-posted to feed!');
            }
        } catch (err) {
            console.error('Error auto-posting focus session:', err);
        }
    }
});
