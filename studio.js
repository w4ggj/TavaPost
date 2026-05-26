let supabaseClient;
const supabaseUrl = "https://fntsthjupopvbwvmfsmz.supabase.co";
const supabaseKey = "sb_publishable_MLMqkdV5LqZsqvq9JhN4kw_XrJvzjAS"; 
const backendBaseUrl = "https://tavapost-backend.onrender.com";

// --- 1. SINGLE INITIALIZATION POINT ---
async function initializeApp() {
    try {
        supabaseClient = supabase.createClient(supabaseUrl, supabaseKey);
        // Do NOT run checkSession() here. 
        // We let the "componentsLoaded" event trigger it.
    } catch (err) {
        console.error("CRITICAL ERROR: ", err);
        const crashAlert = document.getElementById('system-crash-alert');
        if (crashAlert) crashAlert.className = "container view-active-block";
    }
}

// --- 2. EVENT-BASED SYNCING ---
document.addEventListener("componentsLoaded", async () => {
    console.log("Components ready, syncing UI...");
    await checkSession();
});

window.addEventListener('load', initializeApp);

// --- 3. SESSION & UI LOGIC ---
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
        
        try {
            if (typeof handleZernioCallback === 'function') await handleZernioCallback();
            if (typeof loadSettings === 'function') await loadSettings();
            if (typeof loadUsageStats === 'function') await loadUsageStats();
        } catch (err) { console.error("Data load failed:", err); }
    }
}

// --- 4. UTILITY FUNCTIONS ---
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

async function signOutUser() {
    await supabaseClient.auth.signOut();
    localStorage.clear();
    location.reload();
}

function updateFileInputLabel() {
    const fileInput = document.getElementById('imageInput');
    const label = document.getElementById('file-label');
    if(fileInput && fileInput.files.length > 0) {
        label.innerText = `✅ File Selected: ${fileInput.files[0].name}`;
        label.style.color = "var(--accent-green)";
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

async function loadSettings() {
    const { data: { session } } = await supabaseClient.auth.getSession();
    if (!session) return;
    const { data } = await supabaseClient
        .from('user_settings')
        .select('custom_prompt, zernio_facebook_id, zernio_instagram_id')
        .eq('user_id', session.user.id)
        .maybeSingle();
    if (data && data.custom_prompt) document.getElementById('customPrompt').value = data.custom_prompt;
}

async function generateDraft() {
    const fileInput = document.getElementById('imageInput');
    const customPromptElement = document.getElementById('customPrompt');
    const customPromptValue = customPromptElement ? customPromptElement.value : "";

    if (!fileInput.files || fileInput.files.length === 0) return alert("Select an image.");
    
    const { data: { session } } = await supabaseClient.auth.getSession();
    
    try {
        // Prepare JSON payload
        const payload = {
            user_id: session.user.id,
            custom_prompt: customPromptValue
        };

        // We use JSON here for better reliability
        const response = await fetch(`${backendBaseUrl}/generate-draft`, {
    method: "POST",
    headers: { "Authorization": `Bearer ${session.access_token}` },
    body: formData // Keep using FormData as your backend expects
});

        // ... rest of logic

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText);
        }

        const data = await response.json();
        // ... (display logic remains the same)
        
    } catch (err) {
        console.error("Draft error:", err);
        alert("Generation failed: " + err.message);
    } finally {
    // Re-select the element inside the finally block to ensure it exists
    const loading = document.getElementById('loading');
    if (loading) loading.className = "view-section";
    
    if (btnGen) btnGen.disabled = false;
}
}
