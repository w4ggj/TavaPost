// studio.js — TavaOne Studio v2.1.3
const supabaseUrl = "https://fntsthjupopvbwvmfsmz.supabase.co";
const supabaseKey = "sb_publishable_MLMqkdV5LqZsqvq9JhN4kw_XrJvzjAS";
const backendBaseUrl = "https://tavapost-backend.onrender.com";

const supabaseClient = supabase.createClient(supabaseUrl, supabaseKey);

// ─── BOOT ─────────────────────────────────────────────────────────────────────

document.addEventListener("componentsLoaded", async () => {
    console.log("Components ready, syncing UI...");
    await checkSession();
});

// ─── SESSION ──────────────────────────────────────────────────────────────────

async function checkSession() {
    const { data: { session } } = await supabaseClient.auth.getSession();

    const loginView  = document.getElementById('view-login');
    const dashView   = document.getElementById('view-dashboard');
    const logoutBtn  = document.getElementById('header-logout');

    if (!session) {
        if (loginView) loginView.className  = "landing-wrapper view-active-block";
        if (dashView)  dashView.className   = "view-section";
        if (logoutBtn) logoutBtn.className  = "view-section";
    } else {
        if (loginView) loginView.className  = "view-section";
        if (dashView)  dashView.className   = "container view-active-block";
        if (logoutBtn) logoutBtn.className  = "btn btn-logout view-active-block";

        try {
            await handleZernioCallback();
            await loadSettings();
            await loadUsageStats();
        } catch (err) {
            console.error("Data load failed:", err);
        }
    }
}

// ─── ZERNIO OAUTH CALLBACK ────────────────────────────────────────────────────

async function handleZernioCallback() {
    const urlParams = new URLSearchParams(window.location.search);
    const platform  = localStorage.getItem('connecting_platform');

    if (!platform || !urlParams.has('profileId')) return;

    const { data: { session } } = await supabaseClient.auth.getSession();
    if (!session) return;

    try {
        const response = await fetch(`${backendBaseUrl}/api/get-accounts`);
        const data = await response.json();

        if (!data.accounts || data.accounts.length === 0) {
            return alert("Connected but no accounts found in Zernio. Check your dashboard.");
        }

        const match = data.accounts.find(a => a.platform === platform);
        if (!match) {
            return alert(`No ${platform} account found in Zernio. Try connecting again.`);
        }

        let updateData = { user_id: session.user.id };
        if (platform === 'facebook')  updateData.zernio_facebook_id  = match._id;
        if (platform === 'instagram') updateData.zernio_instagram_id = match._id;

        const { error } = await supabaseClient.from('user_settings').upsert(updateData);
        if (!error) {
            window.history.replaceState({}, document.title, window.location.pathname);
            localStorage.removeItem('connecting_platform');
        } else {
            console.error("Supabase write failed:", error);
        }
    } catch (err) {
        console.error("Callback error:", err);
    }
}

// ─── SETTINGS ─────────────────────────────────────────────────────────────────

async function loadSettings() {
    const { data: { session } } = await supabaseClient.auth.getSession();
    if (!session) return;

    const { data, error } = await supabaseClient
        .from('user_settings')
        .select('custom_prompt, zernio_facebook_id, zernio_instagram_id')
        .eq('user_id', session.user.id)
        .maybeSingle();

    if (error) { console.error("loadSettings error:", error); return; }

    if (data) {
        const promptEl = document.getElementById('customPrompt');
        if (promptEl && data.custom_prompt) promptEl.value = data.custom_prompt;

        // Facebook
        const fbStatus = document.getElementById('fb-status');
        const fbAction = document.getElementById('fb-action-area');
        if (data.zernio_facebook_id) {
            window.currentFbId = data.zernio_facebook_id;
            if (fbStatus) { fbStatus.innerText = "Connected ✅"; fbStatus.className = "badge badge-green"; }
            if (fbAction) fbAction.innerHTML = `<button type="button" class="btn btn-disconnect" onclick="disconnectPlatform('facebook')">Disconnect</button>`;
        } else {
            window.currentFbId = null;
            if (fbStatus) { fbStatus.innerText = "Not Connected"; fbStatus.className = "badge badge-red"; }
            if (fbAction) fbAction.innerHTML = `<button type="button" class="btn btn-fb" onclick="connectPlatform('facebook')">Connect Page</button>`;
        }

        // Instagram
        const igStatus = document.getElementById('ig-status');
        const igAction = document.getElementById('ig-action-area');
        if (data.zernio_instagram_id) {
            window.currentIgId = data.zernio_instagram_id;
            if (igStatus) { igStatus.innerText = "Connected ✅"; igStatus.className = "badge badge-green"; }
            if (igAction) igAction.innerHTML = `<button type="button" class="btn btn-disconnect" onclick="disconnectPlatform('instagram')">Disconnect</button>`;
        } else {
            window.currentIgId = null;
            if (igStatus) { igStatus.innerText = "Not Connected"; igStatus.className = "badge badge-red"; }
            if (igAction) igAction.innerHTML = `<button type="button" class="btn btn-ig" onclick="connectPlatform('instagram')">Connect IG</button>`;
        }
    }
}

async function saveSettings() {
    const { data: { session } } = await supabaseClient.auth.getSession();
    if (!session) return alert("Session expired.");

    const inputEl = document.getElementById("customPrompt");
    const customPromptValue = inputEl ? inputEl.value : "";

    const { error } = await supabaseClient
        .from('user_settings')
        .upsert({ user_id: session.user.id, custom_prompt: customPromptValue });

    if (error) {
        alert("Database error: " + error.message);
    } else {
        const status = document.getElementById('save-status');
        if (status) {
            status.className = "text-green view-active-block";
            setTimeout(() => status.className = "view-section", 3000);
        }
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
        const tier = profile.subscription_tier;
        const count = profile.monthly_draft_count;

        // Admin panel logic (revealed for admin or complimentary)
        if (tier === 'admin' || tier === 'complimentary') {
            document.querySelectorAll('.admin-only').forEach(el => el.style.display = 'block');
        }

        if (!counter) return;

        // --- UPDATED TIER LIMIT LOGIC ---
        if (tier === 'admin') {
            counter.innerHTML = `<span style="color: var(--accent-purple); font-weight: bold;">Admin: Unlimited</span>`;
        } else if (tier === 'complimentary') {
            counter.innerHTML = `<span style="color: var(--accent-green); font-weight: bold;">Complimentary: ${count} / 75 Drafts</span>`;
        } else if (tier === 'founders') {
            counter.innerHTML = `<span style="color: var(--accent-green); font-weight: bold;">Founder: ${count} / 50 Drafts</span>`;
        } else {
            // Starter Tier
            counter.innerHTML = `<span style="color: ${count >= 25 ? '#ef4444' : 'var(--accent-blue)'}; font-weight: bold;">${count} / 25 Drafts</span>`;
        }
    } catch (err) {
        console.error("loadUsageStats error:", err);
    }
}

// ─── AUTH ─────────────────────────────────────────────────────────────────────

async function signInUser() {
    const email    = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;
    const { error } = await supabaseClient.auth.signInWithPassword({ email, password });
    if (error) {
        const errorLabel = document.getElementById('login-error');
        if (errorLabel) { errorLabel.innerText = `Login Failed: ${error.message}`; errorLabel.className = "text-red view-active-block"; }
    } else {
        await checkSession();
    }
}

async function signOutUser() {
    await supabaseClient.auth.signOut();
    localStorage.clear();
    location.reload();
}

// ─── PLATFORM CONNECT / DISCONNECT ───────────────────────────────────────────

async function connectPlatform(platform) {
    localStorage.setItem('connecting_platform', platform);

    try {
        const response = await fetch(`${backendBaseUrl}/api/get-connect-url?platform=${platform}`);
        const data = await response.json();

        if (data && data.authUrl) {
            window.location.href = data.authUrl;
        } else {
            throw new Error("authUrl missing from API response.");
        }
    } catch (err) {
        console.error("Connection error:", err);
        alert("Failed to connect: " + err.message);
    }
}

async function disconnectPlatform(platform) {
    const { data: { session } } = await supabaseClient.auth.getSession();
    if (!session) return;

    if (!confirm(`Are you sure you want to disconnect your ${platform} account?`)) return;

    let update = {};
    update[platform === 'facebook' ? 'zernio_facebook_id' : 'zernio_instagram_id'] = null;

    const { error } = await supabaseClient
        .from('user_settings')
        .update(update)
        .eq('user_id', session.user.id);

    if (!error) {
        if (platform === 'facebook')  window.currentFbId = null;
        if (platform === 'instagram') window.currentIgId = null;
        await loadSettings();
        alert("Account disconnected from Studio successfully.");
    } else {
        alert("Database error: " + error.message);
    }
}

// ─── CONTENT PIPELINE ────────────────────────────────────────────────────────

function updateFileInputLabel() {
    const fileInput = document.getElementById('imageInput');
    const label     = document.getElementById('file-label');
    if (fileInput && fileInput.files.length > 0) {
        label.innerText    = `✅ File Selected: ${fileInput.files[0].name}`;
        label.style.color  = "var(--accent-green)";
    }
}

async function generateDraft() {
    const fileInput        = document.getElementById('imageInput');
    const loadingLabel     = document.getElementById('loading');
    const btnGen           = document.getElementById('btn-generate');
    const customPromptEl   = document.getElementById('customPrompt');
    const customPromptValue = customPromptEl ? customPromptEl.value : "";

    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        return alert("Please select an image file first.");
    }

    const { data: { session } } = await supabaseClient.auth.getSession();
    if (!session) return alert("Session expired. Please log in again.");

    if (loadingLabel) loadingLabel.className = "view-active-block";
    if (btnGen) { btnGen.disabled = true; btnGen.classList.add('btn-disabled'); }
    document.getElementById('draft-cards').innerHTML = "";
    document.getElementById('selection-area').className = "view-section";

    try {
        const formData = new FormData();
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

        if (data.image_url) {
            window.cachedImageUrl = data.image_url;
            console.log("Image URL cached for publishing:", window.cachedImageUrl);
        }

        const container = document.getElementById('draft-cards');
        if (container) {
            container.innerHTML = "";

            const options = data.draft_text
                .split("###SEPARATOR###")
                .filter(t => t.trim().length > 20);

            if (options.length === 0) throw new Error("No caption variations returned. Try again.");

            options.forEach((txt, i) => {
                const card = document.createElement('div');
                card.className = "draft-card";
                card.innerHTML = `
                    <header>Draft Variation ${i + 1}</header>
                    <p style="white-space: pre-wrap; line-height: 1.6; font-size: 0.95rem;">${txt.trim()}</p>
                `;
                card.onclick = () => {
                    document.getElementById('finalCaption').value = txt.trim();
                    document.querySelectorAll('.draft-card').forEach(el => el.style.borderColor = "");
                    card.style.borderColor = "var(--accent-green)";
                };
                container.appendChild(card);
            });

            document.getElementById('selection-area').className = "view-active-block";
        }

        await loadUsageStats();

    } catch (err) {
        console.error("Draft generation error:", err);
        alert("Generation failed: " + err.message);
    } finally {
        if (loadingLabel) loadingLabel.className = "view-section";
        if (btnGen) { btnGen.disabled = false; btnGen.classList.remove('btn-disabled'); }
    }
}

async function publishToSocials() {
    const { data: { session } } = await supabaseClient.auth.getSession();
    if (!session) return alert("Session expired. Please log in again.");

    const caption = document.getElementById('finalCaption').value.trim();
    if (!caption) return alert("Please select or write a caption first.");

    const targetFB = document.getElementById('publish-to-fb')?.checked;
    const targetIG = document.getElementById('publish-to-ig')?.checked;
    if (!targetFB && !targetIG) return alert("Please select at least one platform.");

    const platforms = [];
    if (targetFB) {
        if (!window.currentFbId) return alert("Facebook is checked but no account is connected.");
        platforms.push({ platform: 'facebook', accountId: window.currentFbId });
    }
    if (targetIG) {
        if (!window.currentIgId) return alert("Instagram is checked but no account is connected.");
        platforms.push({ platform: 'instagram', accountId: window.currentIgId });
    }

    const btn = document.getElementById('btn-publish');
    if (btn) { btn.disabled = true; btn.innerText = "Publishing..."; }

    try {
        const response = await fetch(`${backendBaseUrl}/publish-post`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${session.access_token}`
            },
            body: JSON.stringify({
                image_url: (window.cachedImageUrl && !window.cachedImageUrl.includes('placeholder'))
                    ? window.cachedImageUrl
                    : "",
                caption: caption,
                platforms: platforms
            })
        });

        const result = await response.json();

        if (result.status === "success") {
            alert("🚀 Successfully published!");
        } else {
            throw new Error(result.detail || JSON.stringify(result));
        }
    } catch (err) {
        console.error("Publish error:", err);
        alert("Publishing failed: " + err.message);
    } finally {
        if (btn) { btn.disabled = false; btn.innerText = "🚀 Publish Directly to Social Channels"; }
    }
}

async function upgradeToPlan(priceId) {
    try {
        const response = await fetch(`${backendBaseUrl}/create-checkout-session`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ price_id: priceId })
        });
        const data = await response.json();
        if (data.url) {
            window.location.href = data.url;
        } else {
            alert("Could not start checkout. Please try again.");
        }
    } catch (err) {
        alert("Checkout error: " + err.message);
    }
}

async function finalizeAccount() {
    const email = document.getElementById('signup-email').value;
    const password = document.getElementById('signup-password').value;

    const { data: pending } = await supabaseClient
        .from('pending_registrations')
        .select('*')
        .eq('email', email)
        .eq('status', 'paid')
        .maybeSingle();

    if (!pending) {
        return alert("No payment record found for this email. Did you complete the subscription?");
    }

    const { data: authData, error: authError } = await supabaseClient.auth.signUp({ email, password });
    if (authError) return document.getElementById('signup-error').innerText = authError.message;

    await supabaseClient.from('user_profiles').upsert({ 
        id: authData.user.id, 
        subscription_tier: 'founders' 
    });

    alert("Registration complete! Welcome to Founders.");
    window.location.href = "index.html";
}

async function provisionUser() {
    const email = document.getElementById('new-user-email').value;
    const password = document.getElementById('new-user-pass').value;
    const tier = document.getElementById('new-user-tier').value;

    const response = await fetch(`${backendBaseUrl}/admin/create-user`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, tier })
    });

    if (response.ok) {
        alert("User created successfully!");
    } else {
        alert("Provisioning failed.");
    }
}
