let supabaseClient;
const supabaseUrl = "https://fntsthjupopvbwvmfsmz.supabase.co";
// NOTE: Use your LONG JWT string (legacy anon key) here if the 'sb_' key fails
const supabaseKey = "sb_publishable_MLMqkdV5LqZsqvq9JhN4kw_XrJvzjAS"; 
const backendBaseUrl = "https://tavapost-backend.onrender.com";

async function initializeApp() {
    try {
        supabaseClient = supabase.createClient(supabaseUrl, supabaseKey);
        await checkSession();
    } catch (err) {
        console.error("CRITICAL ERROR: ", err);
        const crashAlert = document.getElementById('system-crash-alert');
        if (crashAlert) crashAlert.className = "container view-active-block";
    }
}

async function checkSession() {
    const { data: { session } } = await supabaseClient.auth.getSession();
    
    // UI Elements
    const loginView = document.getElementById('view-login');
    const dashView = document.getElementById('view-dashboard');
    const logoutBtn = document.getElementById('header-logout'); // Ensure this ID exists in header.html

    if (!session) {
        if (loginView) loginView.className = "landing-wrapper view-active-block";
        if (dashView) dashView.className = "view-section";
    } else {
        if (loginView) loginView.className = "view-section";
        if (dashView) dashView.className = "container view-active-block";
        
        // Ensure buttons exist before changing their class
        if (logoutBtn) logoutBtn.className = "btn btn-logout view-active-block";
        
        // Only load data if the dashboard is actually visible
        await Promise.all([handleZernioCallback(), loadSettings(), loadUsageStats()]);
    }
}

async function loadUsageStats() {
    const { data: { session } } = await supabaseClient.auth.getSession();
    if (!session) return;
    try {
        const { data: profile } = await supabaseClient
            .from('user_profiles')
            .select('subscription_tier, monthly_draft_count')
            .eq('id', session.user.id)
            .single();
        if (!profile) return;
        const counter = document.getElementById('usage-counter');
        if (counter) {
            counter.innerHTML = profile.subscription_tier === 'founders' 
                ? `<span style="color: var(--accent-green); font-weight: bold;">Unlimited (Founders)</span>`
                : `<span style="color: ${profile.monthly_draft_count >= 25 ? '#ef4444' : 'var(--accent-blue)'}; font-weight: bold;">${profile.monthly_draft_count} / 25 Drafts</span>`;
        }
    } catch (err) { console.error(err); }
}

async function upgradeToPlan(priceId) {
    const response = await fetch(`${backendBaseUrl}/create-checkout-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ price_id: priceId }),
    });
    const data = await response.json();
    if (data.url) window.location.href = data.url;
}

// Start the app when window loads
window.addEventListener('load', initializeApp);
