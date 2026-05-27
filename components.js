// components.js
document.addEventListener("DOMContentLoaded", () => {
    
    // 1. Fetch and inject the Header
    const loadHeader = fetch("header.html")
        .then(response => response.text())
        .then(html => {
            const headerPlaceholder = document.getElementById("header-placeholder");
            if (headerPlaceholder) {
                headerPlaceholder.outerHTML = html;
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
                
                // Set the version number
                const versionEl = document.getElementById("app-version");
                if (versionEl) {
                    versionEl.textContent = "2.1.3";
                }
            }
        }); // <-- THIS WAS MISSING

    // 3. Broadcast that the UI is ready
    Promise.all([loadHeader, loadFooter])
        .then(() => {
            document.dispatchEvent(new Event("componentsLoaded"));
        })
        .catch(error => console.error("Error loading components:", error));
});
