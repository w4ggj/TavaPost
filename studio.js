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

    const { data, error } = await supabaseClient
        .from('user_settings')
        .select('custom_prompt, zernio_facebook_id, zernio_instagram_id')
        .eq('user_id', session.user.id)
        .maybeSingle();

    if (error) return;

    if (data) {
        if (data.custom_prompt) document.getElementById('customPrompt').value = data.custom_prompt;
        
        // --- FACEBOOK: Set global ID and update UI ---
        if (data.zernio_facebook_id) {
            window.currentFbId = data.zernio_facebook_id; // <--- ADD THIS
            const fbStatus = document.getElementById('fb-status');
            const fbAction = document.getElementById('fb-action-area');
            if (fbStatus) {
                fbStatus.innerText = "Connected ✅";
                fbStatus.className = "badge badge-green";
            }
            if (fbAction) {
                fbAction.innerHTML = `<button type="button" class="btn btn-disconnect" onclick="disconnectPlatform('facebook')">Disconnect</button>`;
            }
        }
        
        // --- INSTAGRAM: Set global ID and update UI ---
        if (data.zernio_instagram_id) {
            window.currentIgId = data.zernio_instagram_id; // <--- ADD THIS
            const igStatus = document.getElementById('ig-status');
            const igAction = document.getElementById('ig-action-area');
            if (igStatus) {
                igStatus.innerText = "Connected ✅";
                igStatus.className = "badge badge-green";
            }
            if (igAction) {
                igAction.innerHTML = `<button type="button" class="btn btn-disconnect" onclick="disconnectPlatform('instagram')">Disconnect</button>`;
            }
        }
    }
}
async function generateDraft() {
    // 1. Declare all variables at the top level of the function
    const fileInput = document.getElementById('imageInput');
    const loadingLabel = document.getElementById('loading');
    const btnGen = document.getElementById('btn-generate');
    const customPromptElement = document.getElementById('customPrompt');
    const customPromptValue = customPromptElement ? customPromptElement.value : "";
    
    // Declare formData here so it is accessible in the finally block if needed
    let formData = new FormData(); 

    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        return alert("Please select an image file first.");
    }

    const { data: { session } } = await supabaseClient.auth.getSession();
    if (!session) return alert("Session expired.");

    if (loadingLabel) loadingLabel.className = "view-active-block";
    if (btnGen) btnGen.disabled = true;

    try {
        formData.append("file", fileInput.files[0]);
        formData.append("user_id", session.user.id);
        formData.append("custom_prompt", customPromptValue);

        const response = await fetch(`${backendBaseUrl}/generate-draft`, {
            method: "POST",
            headers: { "Authorization": `Bearer ${session.access_token}` },
            body: formData
        });

        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(errorText);
        }

        const data = await response.json();
        const container = document.getElementById('draft-cards');
        const hiddenUrlField = document.getElementById('finalImageUrl');
        if (hiddenUrlField && data.image_url) {
            hiddenUrlField.value = data.image_url;
        }
        const container = document.getElementById('draft-cards');
        if (container) {
            container.innerHTML = "";
            const options = data.draft_text.split(/(?:Option|Variation)?\s*\d+\.\s*/i).filter(t => t.trim().length > 0);
            options.forEach((txt, i) => {
                const card = document.createElement('div');
                card.className = "draft-card";
                card.innerHTML = `<header>DRAFT VARIATION ${i + 1}</header><p>${txt.trim()}</p>`;
                card.onclick = () => { document.getElementById('finalCaption').value = txt.trim(); };
                container.appendChild(card);
            });
            document.getElementById('selection-area').className = "view-active-block";
        }
    } catch (err) {
        console.error("Draft error:", err);
        alert("Generation failed: " + err.message);
    } finally {
        // Now 'loadingLabel' and 'btnGen' are guaranteed to exist here
        if (loadingLabel) loadingLabel.className = "view-section";
        if (btnGen) btnGen.disabled = false;
    }
}

async function connectPlatform(platform) {
    localStorage.setItem('connecting_platform', platform);
    
    try {
        const response = await fetch(`${backendBaseUrl}/api/get-connect-url?platform=${platform}`);
        const data = await response.json();
        
        console.log("Zernio API Response:", data); 

        // CHANGE: Check for 'authUrl' instead of 'url'
        if (data && data.authUrl) {
            window.location.href = data.authUrl;
        } else {
            throw new Error("API returned success, but authUrl was missing.");
        }
    } catch (err) {
        console.error("Connection error:", err);
        alert("Failed to connect: " + err.message);
    }
}

async function disconnectPlatform(platform) {
    const { data: { session } } = await supabaseClient.auth.getSession();
    
    // Get the correct ID from our settings
    const { data: settings } = await supabaseClient
        .from('user_settings')
        .select('zernio_facebook_id, zernio_instagram_id')
        .eq('user_id', session.user.id)
        .single();

    const accountId = platform === 'facebook' ? settings.zernio_facebook_id : settings.zernio_instagram_id;

    if (!confirm(`Are you sure you want to disconnect your ${platform} account?`)) return;

    try {
        const response = await fetch(`${backendBaseUrl}/disconnect-platform`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account_id: accountId })
        });

        if (response.ok) {
            // Clear from database
            let update = {};
            update[platform === 'facebook' ? 'zernio_facebook_id' : 'zernio_instagram_id'] = null;
            await supabaseClient.from('user_settings').update(update).eq('user_id', session.user.id);
            
            location.reload(); // Refresh to update UI
        } else {
            alert("Failed to disconnect from Zernio.");
        }
    } catch (err) {
        console.error("Disconnect Error:", err);
    }
}

async function publishToSocials() {
    const caption = document.getElementById('finalCaption').value;
    if (!caption) return alert("Please select or write a caption first.");

    // 1. UPDATED IDs to match your HTML
    const fbCheck = document.getElementById('publish-to-fb');
    const igCheck = document.getElementById('publish-to-ig');

    const platforms = [];

    // 2. Use your stored window variables (assuming you set these in loadSettings)
    if (fbCheck?.checked) {
        if (!window.currentFbId) return alert("Facebook ID not loaded. Please refresh.");
        platforms.push({ platform: 'facebook', accountId: window.currentFbId });
    }
    if (igCheck?.checked) {
        if (!window.currentIgId) return alert("Instagram ID not loaded. Please refresh.");
        platforms.push({ platform: 'instagram', accountId: window.currentIgId });
    }

    if (platforms.length === 0) return alert("Select at least one platform.");

    const btn = document.getElementById('btn-publish');
    btn.disabled = true;
    btn.innerText = "Publishing...";

    try {
        const { data: { session } } = await supabaseClient.auth.getSession();
        
        const response = await fetch(`${backendBaseUrl}/publish-post`, {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                "Authorization": `Bearer ${session.access_token}` 
            },
            body: JSON.stringify({
                caption: caption,
                platforms: platforms
            })
        });

        const result = await response.json();
        if (result.status === "success") {
            alert("Successfully published!");
        } else {
            throw new Error(result.detail || "Publishing failed");
        }
    } catch (err) {
        console.error("Publish error:", err);
        alert("Publishing failed: " + err.message);
    } finally {
        btn.disabled = false;
        btn.innerText = "Publish";
    }
}
