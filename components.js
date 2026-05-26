// components.js
document.addEventListener("DOMContentLoaded", () => {
    // Look for the placeholder div
    const footerPlaceholder = document.getElementById("footer-placeholder");
    
    if (footerPlaceholder) {
        fetch("footer.html")
            .then(response => {
                if (!response.ok) throw new Error("Could not load footer.");
                return response.text();
            })
            .then(html => {
                // Inject the HTML
                footerPlaceholder.innerHTML = html;
                // Automatically set the current year
                document.getElementById("current-year").textContent = new Date().getFullYear();
            })
            .catch(error => console.error("Error loading components:", error));
    }
});
