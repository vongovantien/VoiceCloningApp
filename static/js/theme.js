/**
 * Theme Toggle Script
 * Manages dark/light theme switching across the app
 */

(function() {
    const THEME_KEY = 'storytelling_theme';
    
    // Get saved theme or default to dark
    function getTheme() {
        return localStorage.getItem(THEME_KEY) || 'dark';
    }
    
    // Save theme preference
    function saveTheme(theme) {
        localStorage.setItem(THEME_KEY, theme);
    }
    
    // Apply theme to document
    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        
        // Update toggle button icon if exists
        const toggleBtn = document.getElementById('themeToggle');
        if (toggleBtn) {
            const icon = toggleBtn.querySelector('i');
            if (icon) {
                icon.className = theme === 'dark' ? 'fas fa-sun' : 'fas fa-moon';
            }
        }
    }
    
    // Toggle theme
    function toggleTheme() {
        const currentTheme = getTheme();
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        saveTheme(newTheme);
        applyTheme(newTheme);
    }
    
    // Initialize on page load
    function init() {
        // Apply saved theme immediately
        applyTheme(getTheme());
        
        // Attach event listener to toggle button when DOM ready
        document.addEventListener('DOMContentLoaded', function() {
            const toggleBtn = document.getElementById('themeToggle');
            if (toggleBtn) {
                toggleBtn.addEventListener('click', toggleTheme);
            }
        });
    }
    
    // Run initialization
    init();
    
    // Expose globally for manual use
    window.toggleTheme = toggleTheme;
})();
