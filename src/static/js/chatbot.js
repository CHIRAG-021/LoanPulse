/**
 * LoanPulse Customer Support Chatbot Client Module.
 *
 * Handles widget toggle, safe message rendering (XSS prevention),
 * CSRF and Window-ID propagation, suggested questions, and keyboard accessibility.
 */
(function() {
    'use strict';

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initChatbot);
    } else {
        initChatbot();
    }

    function initChatbot() {
        var widget = document.getElementById('lpChatbotWidget');
        if (!widget) return;

        var triggerBtn = document.getElementById('lpChatbotTrigger');
        var panel = document.getElementById('lpChatbotPanel');
        var closeBtn = document.getElementById('lpChatbotClose');
        var minimizeBtn = document.getElementById('lpChatbotMinimize');
        var teaser = document.getElementById('lpChatbotTeaser');
        var teaserClose = document.getElementById('lpChatbotTeaserClose');
        var form = document.getElementById('lpChatbotForm');
        var input = document.getElementById('lpChatbotInput');
        var sendBtn = document.getElementById('lpChatbotSend');
        var msgContainer = document.getElementById('lpChatbotMessages');
        var typingIndicator = document.getElementById('lpChatbotTyping');
        var charCounter = document.getElementById('lpChatbotCharCount');

        var isWaiting = false;

        // Ensure closed state initially
        if (panel) {
            panel.hidden = true;
            panel.style.display = 'none';
            panel.classList.remove('open');
        }
        if (triggerBtn) {
            triggerBtn.setAttribute('aria-expanded', 'false');
        }

        // Retrieve CSRF Token from meta tag
        function getCsrfToken() {
            var meta = document.querySelector('meta[name="csrf-token"]');
            return meta ? meta.getAttribute('content') : '';
        }

        // Retrieve active Tab Window ID from storage
        function getWindowId() {
            try {
                return sessionStorage.getItem('lp_wid') || window.name || '';
            } catch(e) {
                return '';
            }
        }

        function openChat() {
            if (!panel) return;
            panel.hidden = false;
            panel.style.display = 'flex';
            panel.classList.add('open');
            if (triggerBtn) triggerBtn.setAttribute('aria-expanded', 'true');
            if (teaser) teaser.style.display = 'none';
            setTimeout(function() {
                if (input) input.focus();
            }, 100);
            scrollToBottom();
        }

        function closeChat() {
            if (!panel) return;
            panel.classList.remove('open');
            panel.style.display = 'none';
            panel.hidden = true;
            if (triggerBtn) {
                triggerBtn.setAttribute('aria-expanded', 'false');
                triggerBtn.focus();
            }
        }

        if (triggerBtn) {
            triggerBtn.addEventListener('click', function(e) {
                e.preventDefault();
                if (panel && (panel.classList.contains('open') || panel.style.display === 'flex')) {
                    closeChat();
                } else {
                    openChat();
                }
            });
        }

        if (teaser) {
            teaser.addEventListener('click', function(e) {
                if (e.target.closest('#lpChatbotTeaserClose')) return;
                openChat();
            });
        }

        if (teaserClose) {
            teaserClose.addEventListener('click', function(e) {
                e.stopPropagation();
                if (teaser) teaser.style.display = 'none';
                try {
                    sessionStorage.setItem('lp_chat_teaser_dismissed', 'true');
                } catch(err) {}
            });
        }

        // Show teaser bubble gently after 1.5 seconds if not previously dismissed
        try {
            if (sessionStorage.getItem('lp_chat_teaser_dismissed') !== 'true' && teaser) {
                setTimeout(function() {
                    if (panel && !panel.classList.contains('open')) {
                        teaser.style.display = 'flex';
                    }
                }, 1500);
            }
        } catch(e) {}

        if (closeBtn) {
            closeBtn.addEventListener('click', function(e) {
                e.preventDefault();
                closeChat();
            });
        }
        if (minimizeBtn) {
            minimizeBtn.addEventListener('click', function(e) {
                e.preventDefault();
                closeChat();
            });
        }

        // Escape key closes open panel
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && panel && panel.classList.contains('open')) {
                closeChat();
            }
        });

        // Input character count indicator
        if (input && charCounter) {
            input.addEventListener('input', function() {
                var len = input.value.length;
                charCounter.textContent = len + '/500';
                if (len > 500) {
                    charCounter.style.color = 'var(--danger, #dc2626)';
                    if (sendBtn) sendBtn.disabled = true;
                } else {
                    charCounter.style.color = 'var(--text-muted, #64748b)';
                    if (sendBtn) sendBtn.disabled = isWaiting || len === 0;
                }
            });
        }

        // Form submission
        if (form) {
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                if (input) sendMessage(input.value);
            });
        }

        // Event delegation for suggested questions
        if (msgContainer) {
            msgContainer.addEventListener('click', function(e) {
                var chip = e.target.closest('.lp-chip-btn');
                if (chip) {
                    if (isWaiting) {
                        e.preventDefault();
                        e.stopPropagation();
                        return;
                    }
                    var questionText = chip.getAttribute('data-question') || chip.textContent.trim();
                    sendMessage(questionText);
                }
            });
        }

        function scrollToBottom(smooth) {
            if (!msgContainer) return;
            var prefersReduced = false;
            try {
                prefersReduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            } catch (e) {}

            var behavior = (smooth && !prefersReduced) ? 'smooth' : 'auto';
            try {
                if (typeof msgContainer.scrollTo === 'function') {
                    msgContainer.scrollTo({
                        top: msgContainer.scrollHeight,
                        behavior: behavior
                    });
                } else {
                    msgContainer.scrollTop = msgContainer.scrollHeight;
                }
            } catch (err) {
                msgContainer.scrollTop = msgContainer.scrollHeight;
            }
        }

        function appendMessage(sender, text, chips) {
            if (!msgContainer) return;
            var msgDiv = document.createElement('div');
            msgDiv.className = 'lp-chat-msg ' + sender;

            // Safe text rendering: create text nodes / paragraph elements (never raw innerHTML)
            var lines = (text || '').split('\n');
            for (var i = 0; i < lines.length; i++) {
                if (i > 0) msgDiv.appendChild(document.createElement('br'));
                msgDiv.appendChild(document.createTextNode(lines[i]));
            }

            msgContainer.appendChild(msgDiv);

            // Optional suggestion chips below assistant message
            if (sender === 'assistant' && chips && chips.length > 0) {
                var chipsWrap = document.createElement('div');
                chipsWrap.className = 'lp-chatbot-chips';
                for (var j = 0; j < chips.length; j++) {
                    var btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'lp-chip-btn';
                    btn.setAttribute('data-question', chips[j]);
                    btn.textContent = chips[j];
                    chipsWrap.appendChild(btn);
                }
                msgContainer.appendChild(chipsWrap);
            }

            scrollToBottom(true);
        }

        function setWaitingState(waiting) {
            isWaiting = Boolean(waiting);

            if (widget) {
                widget.classList.toggle('is-waiting', isWaiting);
            }

            if (typingIndicator) {
                if (isWaiting) {
                    // Position indicator after latest message
                    if (msgContainer) {
                        msgContainer.appendChild(typingIndicator);
                    }
                    typingIndicator.classList.add('active');
                    typingIndicator.style.display = 'inline-flex';
                    typingIndicator.setAttribute('aria-hidden', 'false');
                } else {
                    typingIndicator.classList.remove('active');
                    typingIndicator.style.display = 'none';
                    typingIndicator.setAttribute('aria-hidden', 'true');
                }
            }

            if (sendBtn) {
                var hasText = input ? input.value.trim().length > 0 : false;
                sendBtn.disabled = isWaiting || !hasText;
                if (isWaiting) {
                    sendBtn.classList.add('is-busy');
                    sendBtn.setAttribute('aria-busy', 'true');
                } else {
                    sendBtn.classList.remove('is-busy');
                    sendBtn.removeAttribute('aria-busy');
                }
            }

            if (input) {
                input.disabled = isWaiting;
                if (!isWaiting) {
                    if (panel && (panel.classList.contains('open') || panel.style.display === 'flex')) {
                        setTimeout(function() {
                            try { input.focus(); } catch (e) {}
                        }, 50);
                    }
                }
            }

            scrollToBottom(true);
        }

        // Natural delay helper: returns ~2.2s (bounded strictly between 2.0s and 2.7s)
        function getTypingDelay(text) {
            var len = (text || '').length;
            var jitter = Math.floor(Math.random() * 180);
            var lengthBonus = Math.min(180, Math.floor(len * 1.5));
            var delayMs = 2100 + jitter + lengthBonus;
            return Math.max(2000, Math.min(2700, delayMs));
        }

        function delay(ms) {
            return new Promise(function(resolve) {
                setTimeout(resolve, ms);
            });
        }

        function sendMessage(rawText) {
            var text = (rawText || '').trim();
            if (!text || text.length > 500 || isWaiting) return;

            // 1. Immediately render the customer's message
            appendMessage('user', text);
            if (input) input.value = '';
            if (charCounter) charCounter.textContent = '0/500';

            // 2. Put widget in waiting/typing state (shows 3-dot animation, locks inputs/chips)
            setWaitingState(true);

            // 3. Coordinate minimum typing delay with backend fetch
            var typingDelayMs = getTypingDelay(text);
            var delayPromise = delay(typingDelayMs);

            var headers = {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            };
            var csrf = getCsrfToken();
            if (csrf) headers['X-CSRFToken'] = csrf;
            var wid = getWindowId();
            if (wid) headers['X-Window-ID'] = wid;

            var fetchPromise = fetch('/chatbot/message', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({ message: text })
            })
            .then(function(res) {
                return res.json().then(function(data) {
                    return { ok: res.ok, status: res.status, data: data };
                }).catch(function() {
                    return { ok: res.ok, status: res.status, data: null };
                });
            })
            .catch(function(err) {
                return { ok: false, status: 0, networkError: true, error: err };
            });

            // Concurrency: Wait for BOTH network response and the ~2.2s typing duration.
            // If backend is slower than 3s, typing indicator stays visible until response arrives.
            // If typing duration already passed when response arrives, display immediately without extra delay.
            Promise.all([fetchPromise, delayPromise])
            .then(function(results) {
                var response = results[0];

                // Remove typing indicator immediately before rendering assistant reply
                setWaitingState(false);

                if (response.networkError) {
                    appendMessage('assistant',
                        'A network connection error occurred while contacting the assistant. Please check your connection and try again.',
                        ['What documents are required for KYC?', 'How do I check my application status?']
                    );
                } else if (response.ok && response.data) {
                    appendMessage('assistant', response.data.reply, response.data.suggested_questions);
                } else if (response.status === 429) {
                    var rateMsg = (response.data && response.data.reply) ||
                        'You have sent several messages quickly. Please wait a moment before asking another question.';
                    appendMessage('assistant', rateMsg);
                } else {
                    var errReply = (response.data && response.data.reply) ||
                        'I encountered a temporary issue processing your question. Please try again or contact support at support@loanpulse.local.';
                    appendMessage('assistant', errReply, [
                        'What documents are required for KYC?',
                        'How many days does it take to get the money?'
                    ]);
                }
            })
            .catch(function(unexpectedErr) {
                console.error('Chatbot unexpected failure:', unexpectedErr);
                setWaitingState(false);
                appendMessage('assistant',
                    'An unexpected error occurred. Please try again or contact support at support@loanpulse.local.',
                    ['What documents are required for KYC?']
                );
            });
        }
    }
})();
