// components.js
document.addEventListener("DOMContentLoaded", () => {
    
    // 1. Fetch and inject the Header
    const loadHeader = fetch("header.html")
        .then(response => response.text())
        .then(html => {
            const headerPlaceholder = document.getElementById("header-placeholder");
            if (headerPlaceholder) {
                headerPlaceholder.outerHTML = html; // Replaces the placeholder with the actual header
                
                // Show the "Return" button if we are on a legal/support page
                const currentPath = window.location.pathname.toLowerCase();
                if (currentPath.includes("privacy") || currentPath.includes("terms") || currentPath.includes("support")) {
                    document.getElementById("header-return").className = "btn btn-logout view-active-block";
                }
            }
        });

    // 2. Fetch and inject the Footer
    const loadFooter = fetch("footer.html")
        .then(response => response.text())
        .then(html => {
            const footerPlaceholder = document.getElementById("footer-placeholder");
            if (footerPlaceholder) {
                footerPlaceholder.innerHTML = html;
                document.getElementById("current-year").textContent = new Date().getFullYear();
                
                // ADD THIS LINE TO SET THE VERSION
                const versionEl = document.getElementById("app-version");
                if (versionEl) {
                    versionEl.textContent = "2.1.3";
                }
            }
        });
