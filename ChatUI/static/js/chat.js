class ChatUI {
    constructor() {
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.chatMessages = document.getElementById('chatMessages');
        this.loadingContainer = document.getElementById('loadingContainer');
        this.exportPdfBtn = document.getElementById('exportPdfBtn');
        this.clearChatBtn = document.getElementById('clearChatBtn');
        this.currentTimeElement = document.getElementById('currentTime');
        this.currentTimezoneElement = document.getElementById('currentTimezone');
        
        this.initializeEventListeners();
        this.startTimeUpdater();
        this.autoResizeTextarea();
        this.scrollToBottom();
        this.setWelcomeMessageTime();
    }

    setWelcomeMessageTime() {
        const welcomeTimeElement = document.getElementById('welcomeTime');
        if (welcomeTimeElement) {
            welcomeTimeElement.textContent = this.getCurrentTimestamp();
        }
    }

    initializeEventListeners() {
        // Send message on button click
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        
        // Send message on Enter key (Shift+Enter for new line)
        this.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Enable/disable send button based on input
        this.messageInput.addEventListener('input', () => {
            this.toggleSendButton();
            this.autoResizeTextarea();
        });
        
        // Export PDF functionality
        this.exportPdfBtn.addEventListener('click', () => this.exportPDF());
        
        // Clear chat functionality
        this.clearChatBtn.addEventListener('click', () => this.clearChat());
    }

    toggleSendButton() {
        const hasText = this.messageInput.value.trim().length > 0;
        this.sendBtn.disabled = !hasText;
    }

    autoResizeTextarea() {
        this.messageInput.style.height = 'auto';
        this.messageInput.style.height = Math.min(this.messageInput.scrollHeight, 120) + 'px';
    }

    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message) return;

        // Clear input and disable send button
        this.messageInput.value = '';
        this.toggleSendButton();
        this.autoResizeTextarea();

        // Add user message to chat
        this.addUserMessage(message);
        
        // Show loading animation
        this.showLoading();
        
        try {
            const startTime = Date.now();
            
            const response = await fetch('/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            });

            const data = await response.json();

            if (response.ok) {
                // Hide loading and add AI response
                this.hideLoading();
                this.addAIMessage(data);
            } else {
                this.hideLoading();
                this.showToast('Error: ' + (data.error || 'Unknown error occurred'), 'error');
            }
        } catch (error) {
            this.hideLoading();
            console.error('Error sending message:', error);
            this.showToast('Failed to send message. Please try again.', 'error');
        }
    }

    addUserMessage(message) {
        const timestamp = this.getCurrentTimestamp();
        const messageHtml = `
            <div class="message user-message">
                <div class="message-content">
                    <div class="message-text">${this.escapeHtml(message)}</div>
                    <div class="message-time">${timestamp}</div>
                </div>
                <div class="user-avatar">
                    <i class="fas fa-user"></i>
                </div>
            </div>
        `;
        
        this.chatMessages.insertAdjacentHTML('beforeend', messageHtml);
        this.scrollToBottom();
    }

    addAIMessage(data) {
        const timestamp = this.getCurrentTimestamp();
        const messageHtml = `
            <div class="message ai-message">
                <div class="ai-avatar">
                    <i class="fas fa-robot"></i>
                </div>
                <div class="message-content">
                    <div class="message-text">${this.escapeHtml(data.response)}</div>
                    <div class="message-footer">
                        <div class="message-meta">
                            <span class="message-time">${timestamp}</span>
                            <span class="response-time">Response time: ${data.response_time}s</span>
                            <span class="token-count">
                                <i class="fas fa-coins"></i> 
                                In: ${data.input_tokens} | Out: ${data.output_tokens}
                            </span>
                        </div>
                        <button class="copy-btn" onclick="copyToClipboard(this)" data-text="${this.escapeHtml(data.response)}">
                            <i class="fas fa-copy"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        this.chatMessages.insertAdjacentHTML('beforeend', messageHtml);
        this.scrollToBottom();
    }

    showLoading() {
        this.loadingContainer.style.display = 'flex';
        this.scrollToBottom();
    }

    hideLoading() {
        this.loadingContainer.style.display = 'none';
    }

    scrollToBottom() {
        setTimeout(() => {
            this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
        }, 100);
    }

    getCurrentTimestamp() {
        const now = new Date();
        return now.toLocaleTimeString('en-US', { 
            hour12: false,
            hour: '2-digit', 
            minute: '2-digit',
            second: '2-digit'
        });
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async exportPDF() {
        try {
            this.showToast('Generating PDF export...', 'info');
            
            const response = await fetch('/export_pdf');
            
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `chat_export_${new Date().getTime()}.pdf`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                window.URL.revokeObjectURL(url);
                
                this.showToast('PDF exported successfully!', 'success');
            } else {
                const data = await response.json();
                this.showToast('Error: ' + (data.error || 'Failed to export PDF'), 'error');
            }
        } catch (error) {
            console.error('Error exporting PDF:', error);
            this.showToast('Failed to export PDF. Please try again.', 'error');
        }
    }

    async clearChat() {
        if (!confirm('Are you sure you want to clear the chat history? This action cannot be undone.')) {
            return;
        }

        try {
            const response = await fetch('/clear_chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });

            if (response.ok) {
                // Clear chat messages except welcome message
                const messages = this.chatMessages.querySelectorAll('.message:not(.welcome-message)');
                messages.forEach(message => message.remove());
                
                // Reset message count
                this.messageCount = 0;
                this.updateExportButtonState();
                
                this.showToast('Chat cleared successfully!', 'success');
            } else {
                this.showToast('Failed to clear chat. Please try again.', 'error');
            }
        } catch (error) {
            console.error('Error clearing chat:', error);
            this.showToast('Failed to clear chat. Please try again.', 'error');
        }
    }

    startTimeUpdater() {
        this.updateTime();
        setInterval(() => this.updateTime(), 1000);
    }

    async updateTime() {
        try {
            const response = await fetch('/get_current_time');
            if (response.ok) {
                const data = await response.json();
                this.currentTimeElement.textContent = data.time;
                this.currentTimezoneElement.textContent = data.timezone;
            }
        } catch (error) {
            // Fallback to client-side time if server request fails
            const now = new Date();
            this.currentTimeElement.textContent = now.toLocaleTimeString('en-US', { 
                hour12: false,
                hour: '2-digit', 
                minute: '2-digit',
                second: '2-digit'
            });
            this.currentTimezoneElement.textContent = Intl.DateTimeFormat().resolvedOptions().timeZone;
        }
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        
        const container = document.getElementById('toastContainer');
        container.appendChild(toast);
        
        // Remove toast after 3 seconds
        setTimeout(() => {
            toast.style.animation = 'toastSlideIn 0.3s ease-out reverse';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, 3000);
    }
}

// Global function for copy to clipboard
function copyToClipboard(button) {
    const text = button.getAttribute('data-text');
    
    if (navigator.clipboard && window.isSecureContext) {
        // Use the Clipboard API when available
        navigator.clipboard.writeText(text).then(() => {
            showCopySuccess(button);
        }).catch(err => {
            console.error('Failed to copy text: ', err);
            fallbackCopyTextToClipboard(text, button);
        });
    } else {
        // Fallback for older browsers
        fallbackCopyTextToClipboard(text, button);
    }
}

function fallbackCopyTextToClipboard(text, button) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-999999px";
    textArea.style.top = "-999999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        document.execCommand('copy');
        showCopySuccess(button);
    } catch (err) {
        console.error('Fallback: Oops, unable to copy', err);
    }
    
    document.body.removeChild(textArea);
}

function showCopySuccess(button) {
    const originalIcon = button.innerHTML;
    button.innerHTML = '<i class="fas fa-check"></i>';
    button.style.background = '#10B981';
    
    setTimeout(() => {
        button.innerHTML = originalIcon;
        button.style.background = '';
    }, 1000);
    
    // Show toast notification
    if (window.chatUI) {
        window.chatUI.showToast('Message copied to clipboard!', 'success');
    }
}

// Initialize chat UI when page loads
document.addEventListener('DOMContentLoaded', () => {
    window.chatUI = new ChatUI();
});