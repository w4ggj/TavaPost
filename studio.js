let supabaseClient;
const supabaseUrl = "https://fntsthjupopvbwvmfsmz.supabase.co";
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
    const loginView = document.getElementById('view-login');
    const dashView = document.getElementById('view-dashboard');
    const logoutBtn = document.getElementById('header-logout');

    if (!session) {
        if (loginView) loginView.className = "landing-wrapper view-active-block";
        if (dashView) dashView.className = "view-section";
    } else {
        if (loginView) loginView.className = "view-section";
        if (dashView) dashView.className = "container view-active-block";
        if (logoutBtn) logoutBtn.className = "btn btn-logout view-active-block";
        
        // SAFE EXECUTION
        try {
            if (typeof handleZernioCallback === 'function') await handleZernioCallback();
            if (typeof loadSettings === 'function') await loadSettings();
            if (typeof loadUsageStats === 'function') await loadUsageStats();
        } catch (err) { console.error("Data load failed:", err); }
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

async function signInUser() {
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    const { error } = await supabaseClient.auth.signInWithPassword({ email, password });
    if (error) {
        const errLabel = document.getElementById('login-error');
        errLabel.innerText = error.message;
        errLabel.className = "text-red view-active-block";
    } else {
        location.reload();
    }
}

async function handleZernioCallback() {
    const platform = localStorage.getItem('connecting_platform');
    const urlParams = new URLSearchParams(window.location.search);
    if (!platform || !urlParams.has('profileId')) return;

    try {
        const response = await fetch(`${backendBaseUrl}/api/get-accounts`);
        const data = await response.json();
        const match = data.accounts?.find(a => a.platform === platform);
        if (match) {
            const { data: { session } } = await supabaseClient.auth.getSession();
            let update = { user_id: session.user.id };
            update[platform === 'facebook' ? 'zernio_facebook_id' : 'zernio_instagram_id'] = match._id;
            await supabaseClient.from('user_settings').upsert(update);
            localStorage.removeItem('connecting_platform');
            window.history.replaceState({}, document.title, window.location.pathname);
        }
    } catch (err) { console.error("Zernio Callback Error:", err); }
}

async function loadSettings() {
    const { data: { session } } = await supabaseClient.auth.getSession();
    if (!session) return;

    const { data, error } = await supabaseClient
        .from('user_settings')
        .select('custom_prompt, zernio_facebook_id, zernio_instagram_id')
        .eq('user_id', session.user.id)
        .maybeSingle();

    if (error) {
        console.error("Database Fetch Error:", error);
        return;
    }

    if (data) {
        if (data.custom_prompt) document.getElementById('customPrompt').value = data.custom_prompt;
        
        // --- FACEBOOK FIX ---
        const fbStatus = document.getElementById('fb-status');
        const fbAction = document.getElementById('fb-action-area');
        if (data.zernio_facebook_id && fbStatus && fbAction) {
            fbStatus.innerText = "Connected ✅";
            fbStatus.className = "badge badge-green";
            fbAction.innerHTML = `<button type="button" class="btn btn-disconnect" onclick="disconnectPlatform('facebook')">Disconnect</button>`;
        }
        
        // --- INSTAGRAM FIX ---
        const igStatus = document.getElementById('ig-status');
        const igAction = document.getElementById('ig-action-area');
        if (data.zernio_instagram_id && igStatus && igAction) {
            igStatus.innerText = "Connected ✅";
            igStatus.className = "badge badge-green";
            igAction.innerHTML = `<button type="button" class="btn btn-disconnect" onclick="disconnectPlatform('instagram')">Disconnect</button>`;
        }
    }
}

window.addEventListener('load', initializeApp);
// Add this event listener to ensure components load FIRST
document.addEventListener("componentsLoaded", async () => {
    console.log("Components ready, syncing UI...");
    await checkSession();
});

// Update initializeApp to NOT run checkSession immediately
async function initializeApp() {
    try {
        supabaseClient = supabase.createClient(supabaseUrl, supabaseKey);
        // We removed checkSession() from here to avoid the race condition
    } catch (err) {
        console.error("CRITICAL ERROR: ", err);
    }
}
// Force button visibility after everything loads
window.addEventListener('load', () => {
    setTimeout(() => {
        const logoutBtn = document.getElementById('header-logout');
        if (logoutBtn) logoutBtn.className = "btn btn-logout view-active-block";
    }, 1000);
});
